import json
import re

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from fastapi.staticfiles import StaticFiles

from app.schemas import (
    ChatRequest,
    ChatResponse,
    GenerationResponse,
    ProductInput,
    ProductOutput,
)
from app.services.ai_service import chat_with_ai, generate_product_content
from app.utils.validation import validate_result

app = FastAPI(
    title="AI Product Assistant",
    description="Чат-помощник для подготовки B2B-карточек товаров",
    version="2.0.0",
)


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


def _build_factual_seo_description(product: ProductInput) -> str:
    """Содержательное резервное SEO-описание манометра из подтверждённых фактов."""
    specs = product.specs or {}
    if "манометр" not in product.name.lower() or not (product.description or "").strip():
        return ""

    def find_spec(*parts):
        for key, value in specs.items():
            key_lower = str(key).lower()
            if any(part in key_lower for part in parts) and value not in (None, ""):
                return str(value)
        return None

    measurement_range = find_spec("диапазон измер")
    accuracy = find_spec("класс точности")
    connection = find_spec("присоедин")
    diameter = find_spec("диаметр корпуса", "диаметр")
    if not all((measurement_range, accuracy, connection, diameter)):
        return ""

    manufacturer = f" производства {product.manufacturer}" if product.manufacturer else ""
    paragraphs = [
        f"{product.name}{manufacturer} предназначен для измерения избыточного давления. "
        "В карточке указаны диапазон измерений, класс точности, присоединение и диаметр корпуса.",
        f"Диапазон измерений — {measurement_range}. Сопоставьте его с ожидаемым давлением "
        "в точке контроля. Класс точности — " + accuracy + ". Проверьте соответствие этого "
        "значения требованиям измерительной задачи и документации оборудования.",
        f"Присоединение — {connection}. Перед заказом сверьте его с резьбой ответной части. "
        f"Диаметр корпуса — {diameter}. Учитывайте размер при проверке места установки "
        "и возможности считывать показания после монтажа.",
        "В исходном описании подтверждено назначение прибора — измерение избыточного давления. "
        "Материал корпуса, рабочая температура, степень защиты, расположение штуцера и комплект "
        "поставки не указаны. При необходимости запросите эти сведения в паспорте или у поставщика.",
        "Перед покупкой проверьте диапазон и класс точности по требованиям точки измерения, "
        "присоединение — по ответной резьбе, диаметр корпуса — по условиям размещения. "
        "Совместимость с конкретной системой следует подтвердить по документации производителя.",
    ]
    text = "\n\n".join(paragraphs)
    return text if 800 <= len(text) <= 1200 else ""


def _build_commercial_block(product: ProductInput) -> str:
    """Формирует коммерческий блок без неподтверждённых областей применения."""
    name = product.name.strip()
    manufacturer = f" производства {product.manufacturer}" if product.manufacturer else ""
    description = (product.description or "").strip().rstrip(".")
    if "манометр" in name.lower() and description:
        specs = product.specs or {}
        known = "; ".join(f"{key}: {value}" for key, value in specs.items() if value not in (None, ""))
        detail = f" В карточке указаны {known}." if known else ""
        return (
            f"Потенциальный покупатель — организация, которой требуется контролировать избыточное "
            f"давление в своей системе. {name}{manufacturer}: {description[0].lower() + description[1:]}."
            f"{detail} Менеджеру перед предложением следует сверить диапазон, класс точности, "
            "присоединение и монтажные размеры с требованиями заказчика, а недостающие параметры "
            "уточнить по паспорту изделия."
        )
    if description:
        return (
            f"{name}{manufacturer}. {description[0].upper() + description[1:]}. "
            "Для предложения заказчику необходимо сопоставить подтверждённые характеристики "
            "с его техническими требованиями."
        )
    return (
        f"{name}{manufacturer}. В исходных данных недостаточно сведений, чтобы достоверно "
        "описать назначение и область применения товара. До подготовки предложения запросите "
        "описание производителя и техническую документацию."
    )



def _build_incomplete_product_output(product: ProductInput) -> ProductOutput:
    """Возвращает честный черновик, если исходных данных недостаточно для SEO-текста."""
    name = product.name.strip()
    manufacturer = (product.manufacturer or "").strip()
    category = (product.category or "").strip()
    article = (product.article or "").strip()

    title_parts = [name]
    if manufacturer and len(" ".join(title_parts + [manufacturer])) <= 70:
        title_parts.append(manufacturer)
    title = " — ".join(title_parts)

    known = []
    if category:
        known.append(f"Категория: {category}.")
    if article:
        known.append(f"Артикул: {article}.")
    if product.price is not None:
        known.append(f"Цена во входных данных: {product.price:g}.")
    if product.url:
        known.append("Ссылка на товар передана во входных данных.")

    facts = " ".join(known)
    description = (
        f"{name}"
        + (f" — товар производителя {manufacturer}." if manufacturer else ".")
        + (f" {facts}" if facts else "")
        + " Полноценное SEO-описание пока не подготовлено: во входных данных отсутствуют "
        "подтверждённое описание товара и/или технические характеристики. Запросите у "
        "производителя назначение, параметры и техническую документацию. До получения этих "
        "сведений не следует публиковать расширенное описание или делать выводы о свойствах "
        "и совместимости товара."
    )

    queries = [name.lower()]
    if manufacturer:
        queries.append(f"{manufacturer.lower()} {name.lower()}")
    if category:
        queries.append(f"{name.lower()} {category.lower()}")
    if article:
        queries.append(f"{name.lower()} артикул {article}")
    queries = list(dict.fromkeys(queries))[:5]
    while len(queries) < 3:
        queries.append(f"купить {name.lower()}" if len(queries) == 1 else f"{name.lower()} характеристики")

    missing = _get_missing_data(product, [])
    if not product.description or not product.specs:
        missing.append("Подтверждённое SEO-описание (недостаточно исходных данных для подготовки)")

    return ProductOutput(
        seo_title=title[:70],
        seo_description=description,
        characteristics=product.specs or {},
        search_queries=queries,
        commercial_block=_build_commercial_block(product),
        missing_data=list(dict.fromkeys(missing)),
        seo_description_status="needs_data",
        warnings=[
            "SEO-описание не готово к публикации: дополните исходные данные и повторите генерацию."
        ],
    )

def _build_product_output(product: ProductInput) -> ProductOutput:
    # Для исходных записей без описания или характеристик не просим LLM заполнять пробелы догадками.
    if not (product.description or "").strip() or not (product.specs or {}):
        return _build_incomplete_product_output(product)

    product_data = product.model_dump(exclude_none=True)
    feedback = None
    errors = []
    factual_description = _build_factual_seo_description(product)

    # Повторяем генерацию, если модель не соблюла формат или длину SEO-полей.
    for attempt in range(3):
        ai_result = generate_product_content(product_data, feedback=feedback)
        try:
            queries = ai_result.get("search_queries", [])
            if not isinstance(queries, list):
                queries = []
            result = ProductOutput(
                seo_title=str(ai_result.get("seo_title") or "").strip(),
                seo_description=(
                    factual_description
                    or str(ai_result.get("seo_description") or "").strip()
                ),
                # Характеристики никогда не берём из ответа LLM.
                characteristics=product.specs or {},
                search_queries=queries,
                commercial_block=_build_commercial_block(product),
                missing_data=_get_missing_data(product, ai_result.get("missing_data", [])),
            )
        except Exception as error:
            raise ValueError(f"Не удалось собрать результат модели: {error}") from error

        errors = validate_result(result)
        if not errors:
            return result

        feedback = (
            f"В предыдущем ответе обнаружены ошибки: {'; '.join(errors)}. "
            "Исправь их. SEO description должен содержать 800–1200 символов с пробелами. "
            "Используй только факты из входного JSON, не повторяй фразы и не выдумывай свойства. "
            "Верни полный JSON."
        )

    # Qwen 2.5 3B часто возвращает короткий текст даже после повторного запроса.
    # В таком случае собираем описание программно из исходных фактов.
    fallback_description = _build_factual_seo_description(product)
    if fallback_description:
        result.seo_description = fallback_description
        errors = validate_result(result)
        if not errors:
            return result

    # Короткое описание при наличии исходных данных — не авария приложения.
    # Возвращаем полезный черновик, явно помечая, что SEO-текст нельзя публиковать.
    description_only_errors = all(
        error.startswith("SEO description содержит") for error in errors
    )
    if description_only_errors:
        result.seo_description_status = "needs_data"
        result.warnings = list(dict.fromkeys(
            [*(result.warnings or []),
             "Модель подготовила краткий черновик, но его объёма недостаточно для SEO-публикации. "
             "Добавьте подтверждённые сведения из паспорта или документации производителя."]
        ))
        result.missing_data = list(dict.fromkeys(
            [*(result.missing_data or []),
             "Дополнительное описание из технической документации для подготовки SEO-текста объёмом 800–1200 символов"]
        ))
        errors = validate_result(result)
        if not errors:
            return result

    raise ValueError(
        "Не удалось сформировать SEO description длиной 800–1200 символов без выдумывания данных. "
        "Добавьте подробное описание товара и хотя бы три подтверждённые характеристики. "
        "Последняя ошибка модели: " + "; ".join(errors)
    )


def _get_missing_data(product: ProductInput, model_missing) -> list[str]:
    if isinstance(model_missing, str):
        model_missing = [model_missing]
    if not isinstance(model_missing, list):
        model_missing = []

    placeholders = {"нет", "нет.", "отсутствует", "отсутствуют", "данных нет", "не требуется"}
    missing = [
        str(item).strip()
        for item in model_missing
        if str(item).strip() and str(item).strip().lower() not in placeholders
    ]

    if not product.manufacturer:
        missing.append("Производитель")
    if not product.description:
        missing.append("Подробное описание и подтверждённое назначение товара")
    if not product.specs:
        missing.append("Технические характеристики")
    if not product.url:
        missing.append("Ссылка на карточку производителя или техническую документацию")

    if "манометр" in product.name.lower():
        known = " ".join(str(key).lower() for key in (product.specs or {}).keys())
        for key, label in (
            ("материал корпуса", "Материал корпуса"),
            ("температур", "Рабочая температура"),
            ("степень защиты", "Степень защиты"),
            ("расположение штуцера", "Расположение штуцера"),
            ("комплект", "Комплект поставки"),
        ):
            if key not in known:
                missing.append(label)

    return list(dict.fromkeys(missing))

def _format_product(result: ProductOutput) -> str:
    specs = "\n".join(
        f"- **{key}:** {value}" for key, value in result.characteristics.items()
    ) or "- Данных нет"
    queries = "\n".join(f"- {query}" for query in result.search_queries)
    missing = "\n".join(f"- {item}" for item in result.missing_data) or "- Нет"

    heading = "## Карточка товара готова" if result.seo_description_status == "ready" else "## Черновик карточки: нужны исходные данные"
    return (
        heading + "\n\n"
        f"**SEO title** ({len(result.seo_title)} символов)\n\n"
        f"{result.seo_title}\n\n"
        f"**SEO description** ({len(result.seo_description)} символов)\n\n"
        f"{result.seo_description}\n\n"
        + ("**Статус:** требуется дополнить исходные данные\n\n" + "\n".join(f"- {item}" for item in result.warnings) + "\n\n" if result.warnings else "")
        + f"**Характеристики**\n\n{specs}\n\n"
        f"**Поисковые запросы**\n\n{queries}\n\n"
        f"**Коммерческий блок**\n\n{result.commercial_block}\n\n"
        f"**Недостающие данные**\n\n{missing}"
    )


def _extract_json(text: str):
    """Принимает JSON как обычный текст или внутри markdown code fence."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) and "name" in value else None


@app.post("/generate", response_model=GenerationResponse)
def generate(product: ProductInput):
    try:
        result = _build_product_output(product)
        return GenerationResponse(product_id=product.id, result=result)
    except requests.exceptions.RequestException as error:
        raise HTTPException(status_code=503, detail=f"Ошибка подключения к Ollama: {error}") from error
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    messages = [message.model_dump() for message in request.messages]
    last_message = messages[-1]["content"]
    product_data = _extract_json(last_message)

    if product_data is None and last_message.lstrip().startswith(("{", "[")):
        raise HTTPException(status_code=400, detail="Некорректный JSON товара. Проверьте кавычки, запятые и скобки.")

    if product_data is not None:
        try:
            product = ProductInput.model_validate(product_data)
            result = _build_product_output(product)
            return ChatResponse(message=_format_product(result), product=result)
        except requests.exceptions.RequestException as error:
            raise HTTPException(status_code=503, detail=f"Не удалось подключиться к Ollama: {error}") from error
        except Exception as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    try:
        answer = chat_with_ai(messages)
        return ChatResponse(message=answer)
    except requests.exceptions.RequestException as error:
        raise HTTPException(status_code=503, detail=f"Не удалось подключиться к Ollama: {error}") from error
    except ValueError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

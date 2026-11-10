import json
import os

import requests
from dotenv import load_dotenv

from app.prompts.product_prompt import CHAT_SYSTEM_PROMPT, SYSTEM_PROMPT

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")


def _ollama_chat(messages: list[dict], *, json_format: bool = False) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.15,
            "top_p": 0.85,
            "num_predict": 1800,
        },
    }
    if json_format:
        payload["format"] = "json"

    response = requests.post(OLLAMA_URL, json=payload, timeout=300)
    response.raise_for_status()

    data = response.json()
    content = data.get("message", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Ollama вернула пустой ответ")
    return content.strip()


def _parse_model_json(content: str) -> dict:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Модель вернула некорректный JSON")
        try:
            result = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as error:
            raise ValueError(f"Модель вернула некорректный JSON: {error}") from error

    if not isinstance(result, dict):
        raise ValueError("Ответ модели должен быть JSON-объектом")
    return result


def generate_product_content(product_data: dict, feedback: str | None = None) -> dict:
    """Генерирует SEO-текст. Технические характеристики формируются отдельно из входа."""
    user_content = json.dumps(product_data, ensure_ascii=False, indent=2)
    if feedback:
        user_content += (
            "\n\nОБЯЗАТЕЛЬНО ИСПРАВЬ ПРЕДЫДУЩИЙ РЕЗУЛЬТАТ:\n"
            + feedback
            + "\nВерни полный JSON по исходным данным выше."
        )

    content = _ollama_chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        json_format=True,
    )
    return _parse_model_json(content)


def chat_with_ai(messages: list[dict]) -> str:
    """Обычный диалог с моделью с передачей истории сообщений."""
    return _ollama_chat(
        [{"role": "system", "content": CHAT_SYSTEM_PROMPT}, *messages]
    )

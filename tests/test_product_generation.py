import unittest
from unittest.mock import patch

from app.main import (
    _build_factual_seo_description,
    _build_product_output,
    _extract_json,
    _format_product,
)
from app.schemas import ProductInput


class ProductGenerationTests(unittest.TestCase):
    def test_manometer_description_is_within_limit_and_uses_real_newlines(self):
        product = ProductInput(
            name="Манометр показывающий DM 02",
            manufacturer="Манотомь",
            specs={
                "диапазон измерений": "0–1,6 МПа",
                "класс точности": "1,5",
                "присоединение": "G1/2",
                "диаметр корпуса": "100 мм",
            },
            description="Прибор предназначен для измерения избыточного давления.",
        )
        description = _build_factual_seo_description(product)
        self.assertGreaterEqual(len(description), 800)
        self.assertLessEqual(len(description), 1200)
        self.assertIn("\n\n", description)
        self.assertNotIn("\\n", description)

    def test_characteristics_are_copied_from_input(self):
        product = ProductInput(
            name="Манометр показывающий DM 02",
            manufacturer="Манотомь",
            specs={
                "диапазон измерений": "0–1,6 МПа",
                "класс точности": "1,5",
                "присоединение": "G1/2",
                "диаметр корпуса": "100 мм",
            },
            description="Прибор предназначен для измерения избыточного давления.",
        )
        fake_ai = {
            "seo_title": "Манометр DM 02 — Манотомь",
            "seo_description": "Короткий ответ модели",
            "search_queries": ["манометр dm 02", "манотомь dm 02", "манометр 1,6 МПа"],
            "missing_data": [],
        }
        with patch("app.main.generate_product_content", return_value=fake_ai):
            result = _build_product_output(product)
        self.assertEqual(result.characteristics, product.specs)
        self.assertEqual(len(result.seo_description), 1108)
        self.assertIn("Расположение штуцера", result.missing_data)
        self.assertNotIn("\\n", _format_product(result))

    def test_sparse_product_is_not_filled_by_llm(self):
        product = ProductInput(
            name="МК110-224.8Д.4Р [М01]",
            manufacturer="ОВЕН",
            specs={},
            description="",
            category="Модули ввода-вывода",
            article="58953",
            url="https://www.souz-pribor.ru/product/mk110-8d-4r/",
            price=12993,
        )
        with patch("app.main.generate_product_content") as mocked:
            result = _build_product_output(product)
        mocked.assert_not_called()
        self.assertEqual(result.seo_description_status, "needs_data")
        self.assertEqual(result.characteristics, {})
        self.assertIn("Технические характеристики", result.missing_data)
        self.assertIn("нужны исходные данные", _format_product(result))


    def test_short_llm_description_returns_incomplete_draft_instead_of_error(self):
        product = ProductInput(
            name="Тестовый датчик давления ДД-10",
            manufacturer="Тестовый производитель",
            specs={
                "диапазон измерений": "0–10 бар",
                "выходной сигнал": "4–20 мА",
                "напряжение питания": "24 В DC",
            },
            description="Тестовый прибор для проверки генерации карточек.",
        )
        fake_ai = {
            "seo_title": "Тестовый датчик давления ДД-10",
            "seo_description": "Краткое описание на 363 символа. " * 12,
            "search_queries": ["датчик давления дд-10", "датчик 0–10 бар", "датчик 4–20 мА"],
            "missing_data": [],
        }
        with patch("app.main.generate_product_content", return_value=fake_ai):
            result = _build_product_output(product)
        self.assertEqual(result.seo_description_status, "needs_data")
        self.assertTrue(result.seo_description)
        self.assertIn("Дополнительное описание", " ".join(result.missing_data))
        self.assertIn("нужны исходные данные", _format_product(result))

    def test_extract_json_accepts_code_fence_and_rejects_invalid(self):
        self.assertEqual(_extract_json('```json\n{"name":"Тест"}\n```'), {"name": "Тест"})
        self.assertIsNone(_extract_json('{"name": '))


if __name__ == "__main__":
    unittest.main()

from typing import Any

from pydantic import BaseModel, Field


class ProductInput(BaseModel):
    """Исходные данные товара. Технические характеристики не генерируются моделью."""

    id: str | None = None
    name: str = Field(min_length=1)
    manufacturer: str | None = None
    specs: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None

    # Необязательные поля из товарного фида.
    category: str | None = None
    article: str | None = None
    url: str | None = None
    price: float | None = None


class ProductOutput(BaseModel):
    seo_title: str
    seo_description: str
    characteristics: dict[str, Any]
    search_queries: list[str]
    commercial_block: str
    missing_data: list[str]
    seo_description_status: str = "ready"
    warnings: list[str] = Field(default_factory=list)


class GenerationResponse(BaseModel):
    product_id: str | None = None
    result: ProductOutput


class ChatMessage(BaseModel):
    role: str
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)


class ChatResponse(BaseModel):
    message: str
    product: ProductOutput | None = None

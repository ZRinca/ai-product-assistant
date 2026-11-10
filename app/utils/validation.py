def validate_result(result):
    errors = []

    title = result.seo_title.strip()
    if not title:
        errors.append("SEO title не должен быть пустым")
    elif len(title) > 70:
        errors.append(f"SEO title содержит {len(title)} символов, максимум 70")

    description_length = len(result.seo_description.strip())
    if result.seo_description_status == "ready":
        if not 800 <= description_length <= 1200:
            errors.append(
                f"SEO description содержит {description_length} символов, "
                "требуется от 800 до 1200"
            )
    elif not result.seo_description.strip():
        errors.append("Для неполной карточки нужно кратко объяснить, каких данных не хватает")

    queries = result.search_queries
    if not isinstance(queries, list) or not 3 <= len(queries) <= 5:
        errors.append("Количество поисковых запросов должно быть от 3 до 5")
    elif any(not isinstance(query, str) or not query.strip() for query in queries):
        errors.append("Поисковые запросы должны быть непустыми строками")

    if not result.commercial_block.strip():
        errors.append("Коммерческий блок не должен быть пустым")

    return errors

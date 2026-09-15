from django.db.models import Q

from catalog.models import Product


def _term_query(term):
    return (
        Q(name__icontains=term)
        | Q(short_name__icontains=term)
        | Q(subtitle__icontains=term)
        | Q(short_description__icontains=term)
        | Q(description__icontains=term)
        | Q(meta_title__icontains=term)
        | Q(meta_description__icontains=term)
        | Q(category__name__icontains=term)
        | Q(category__description__icontains=term)
        | Q(brand__name__icontains=term)
        | Q(brand__description__icontains=term)
        | Q(variants__name__icontains=term)
        | Q(variants__sku__icontains=term)
        | Q(variants__barcode__icontains=term)
        | Q(variants__variant_values__value__value__icontains=term)
        | Q(variants__variant_values__value__attribute__name__icontains=term)
        | Q(specifications__name__icontains=term)
        | Q(specifications__value__icontains=term)
    )


def matching_product_ids(query):
    """Return active storefront product ids that match every search term."""
    terms = [term for term in str(query or "").split() if term]
    if not terms:
        return []

    queryset = Product.objects.filter(
        status=Product.Status.ACTIVE,
        category__is_active=True,
        brand__is_active=True,
    )
    for term in terms:
        queryset = queryset.filter(_term_query(term))
    return list(queryset.values_list("pk", flat=True).distinct())


def product_search_rank(product, query):
    """Rank serialized products so direct identity matches appear before broad text matches."""
    query = str(query or "").strip().casefold()
    if not query:
        return 0

    name = str(product.get("name") or "").casefold()
    brand = str(product.get("brand") or "").casefold()
    category = str(product.get("category") or "").casefold()
    short_name = str(product.get("short_name") or "").casefold()
    subtitle = str(product.get("subtitle") or "").casefold()
    description = " ".join(
        [
            str(product.get("short_description") or ""),
            str(product.get("description") or ""),
        ]
    ).casefold()

    variants = product.get("variants") or []
    variant_identity = " ".join(
        " ".join(
            [
                str(variant.get("name") or ""),
                str(variant.get("sku") or ""),
                str(variant.get("barcode") or ""),
                " ".join(str(value.get("value") or "") for value in (variant.get("values") or [])),
            ]
        )
        for variant in variants
    ).casefold()
    specifications = " ".join(
        f'{spec.get("name", "")} {spec.get("value", "")}' for spec in (product.get("specifications") or [])
    ).casefold()

    score = 0
    if name == query:
        score += 1000
    elif name.startswith(query):
        score += 850
    elif query in name:
        score += 700
    if short_name == query:
        score += 650
    elif query in short_name:
        score += 500
    if brand == query:
        score += 600
    elif query in brand:
        score += 400
    if category == query:
        score += 580
    elif query in category:
        score += 380
    if query in variant_identity:
        score += 320
    if query in subtitle:
        score += 220
    if query in specifications:
        score += 180
    if query in description:
        score += 100

    for term in query.split():
        if term in name:
            score += 60
        if term in brand or term in category:
            score += 35
        if term in variant_identity:
            score += 25
        if term in specifications:
            score += 18
        if term in description or term in subtitle:
            score += 8
    return score

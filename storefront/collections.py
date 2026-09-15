from django.db.models import Sum

from sales.models import SalesOrder, SalesOrderItem


COLLECTION_LABELS = {
    "best-selling": "Best Selling",
    "new-arrivals": "New Arrivals",
    "special-offers": "Special Offers",
}


def normalize_collection(value):
    key = str(value or "").strip().lower()
    return key if key in COLLECTION_LABELS else ""


def collection_label(value):
    return COLLECTION_LABELS.get(normalize_collection(value), "")


def _best_selling_products(catalog):
    by_pk = {product["pk"]: product for product in catalog}
    if not by_pk:
        return []

    sold_rows = (
        SalesOrderItem.objects.filter(
            order__status=SalesOrder.Status.COMPLETED,
            variant__product_id__in=by_pk,
        )
        .values("variant__product_id")
        .annotate(sold_quantity=Sum("quantity"))
        .order_by("-sold_quantity", "variant__product_id")
    )
    ranked = [by_pk[row["variant__product_id"]] for row in sold_rows if row["variant__product_id"] in by_pk]
    if ranked:
        return ranked

    featured = [product for product in catalog if product.get("is_featured")]
    return featured or list(catalog)


def collection_products(catalog, collection):
    key = normalize_collection(collection)
    rows = list(catalog)
    if key == "best-selling":
        return _best_selling_products(rows)
    if key == "new-arrivals":
        return sorted(
            [product for product in rows if product.get("is_new_arrival")],
            key=lambda product: product.get("created_at") or "",
            reverse=True,
        )
    if key == "special-offers":
        return [
            product
            for product in rows
            if float(product.get("price") or 0) < float(product.get("regular_price") or 0)
        ]
    return rows

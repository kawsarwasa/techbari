"""Display helpers shared by the static storefront and dashboard."""
from django import template
register = template.Library()

@register.filter
def money(value):
    try:
        return f"৳ {float(value):,.0f}"
    except (TypeError, ValueError):
        return "৳ 0"

@register.filter
def get_item(record, key):
    return record.get(key, "")

@register.filter
def status_class(value):
    text = str(value).lower()
    for color, words in (
        ("green", ("active", "delivered", "paid", "received", "success", "posted", "approved", "in stock")),
        ("blue", ("processing", "shipped", "in transit", "partial")),
        ("orange", ("pending", "low stock", "inspection")),
        ("red", ("out of stock", "cancel", "reject", "failed")),
    ):
        if any(word in text for word in words):
            return color
    return "gray"

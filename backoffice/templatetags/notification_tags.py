from django import template

register = template.Library()

_LEVELS = {"success", "error", "warning", "info"}


def _normalise_level(value):
    text = str(value or "").lower()
    for level in _LEVELS:
        if level in text.split():
            return level
    if "danger" in text:
        return "error"
    return "info"


def _page_message_parts(message):
    if isinstance(message, dict):
        text = message.get("text") or message.get("message") or ""
        level = message.get("level") or message.get("type") or message.get("tags") or "info"
        return str(text), _normalise_level(level)
    text = getattr(message, "text", None) or getattr(message, "message", None) or str(message)
    level = getattr(message, "level_tag", None) or getattr(message, "tags", None) or "info"
    return str(text), _normalise_level(level)


@register.simple_tag(takes_context=True)
def collect_toast_messages(context):
    """Collect project-wide action notices into one Toastr-compatible payload.

    Backoffice modules currently expose action feedback in two ways:
    Django's messages framework and context variables such as catalog_notice,
    inventory_error or purchase_notice. This tag normalises both without
    forcing every CRUD view to be rewritten at once.
    """
    flat = context.flatten()
    result = []
    seen = set()

    def add(level, text, source=""):
        text = str(text or "").strip()
        if not text:
            return
        level = _normalise_level(level)
        key = (level, text)
        if key in seen:
            return
        seen.add(key)
        result.append({"level": level, "message": text, "source": source})

    django_messages = flat.get("messages")
    if django_messages:
        for message in django_messages:
            text = str(message).strip()
            level = getattr(message, "level_tag", None) or getattr(message, "tags", None) or "info"
            add(level, text, "django")

    for message in flat.get("page_messages") or []:
        text, level = _page_message_parts(message)
        add(level, text, "page")

    for key, value in flat.items():
        key_lower = str(key).lower()
        if key_lower in {"messages", "page_messages"} or not isinstance(value, str):
            continue
        if key_lower.endswith("_form_error"):
            # Keep form/service validation errors inline beside the fields.
            continue
        if key_lower.endswith("_notice"):
            add("success", value, key_lower)
        elif key_lower.endswith("_error"):
            add("error", value, key_lower)
        elif key_lower.endswith("_warning"):
            add("warning", value, key_lower)
        elif key_lower.endswith("_info"):
            add("info", value, key_lower)

    return result

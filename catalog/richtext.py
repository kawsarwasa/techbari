import re
from html import escape
from html.parser import HTMLParser


_ALLOWED_TAGS = {
    "p",
    "div",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "ul",
    "ol",
    "li",
    "h2",
    "h3",
    "blockquote",
    "span",
}
_ALLOWED_FONT_SIZES = {"12px", "14px", "16px", "18px", "20px", "24px", "28px", "32px"}
_SAFE_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_VOID_TAGS = {"br"}
_DROP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed"}


def _safe_span_style(attrs):
    attributes = {str(name).lower(): (value or "") for name, value in attrs}
    raw_style = attributes.get("style", "")
    safe = []
    for declaration in raw_style.split(";"):
        if ":" not in declaration:
            continue
        name, value = declaration.split(":", 1)
        name = name.strip().lower()
        value = value.strip().lower()
        if name == "font-size" and value in _ALLOWED_FONT_SIZES:
            safe.append(f"font-size:{value}")
        elif name == "color" and _SAFE_HEX_COLOR.fullmatch(value):
            safe.append(f"color:{value}")
    return ";".join(safe)


class _RichTextSanitizer(HTMLParser):
    """Allow formatting-only HTML and discard executable/embedded content."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.drop_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _DROP_CONTENT_TAGS:
            self.drop_depth += 1
            return
        if self.drop_depth:
            return
        if tag in _ALLOWED_TAGS:
            if tag == "span":
                style = _safe_span_style(attrs)
                self.parts.append(f'<span style="{style}">' if style else "<span>")
            else:
                self.parts.append(f"<{tag}>")

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if self.drop_depth or tag in _DROP_CONTENT_TAGS:
            return
        if tag in _ALLOWED_TAGS:
            if tag == "span":
                style = _safe_span_style(attrs)
                self.parts.append(f'<span style="{style}">' if style else "<span>")
            else:
                self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _DROP_CONTENT_TAGS:
            if self.drop_depth:
                self.drop_depth -= 1
            return
        if self.drop_depth:
            return
        if tag in _ALLOWED_TAGS and tag not in _VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.drop_depth:
            self.parts.append(escape(data))

    def handle_comment(self, data):
        return


def sanitize_rich_html(value):
    if not value:
        return ""
    parser = _RichTextSanitizer()
    parser.feed(str(value))
    parser.close()
    return "".join(parser.parts).strip()


def inline_rich_html(value):
    """Legacy inline-safe rendering kept for backwards compatibility."""

    html = sanitize_rich_html(value)
    if not html:
        return ""

    replacements = (
        ("<p>", ""),
        ("</p>", "<br><br>"),
        ("<div>", ""),
        ("</div>", "<br>"),
        ("<h2>", "<strong>"),
        ("</h2>", "</strong><br>"),
        ("<h3>", "<strong>"),
        ("</h3>", "</strong><br>"),
        ("<blockquote>", "“"),
        ("</blockquote>", "”<br>"),
        ("<ul>", ""),
        ("</ul>", ""),
        ("<ol>", ""),
        ("</ol>", ""),
        ("<li>", "• "),
        ("</li>", "<br>"),
    )
    for old, new in replacements:
        html = html.replace(old, new)
    while html.endswith("<br>"):
        html = html[:-4]
    return html

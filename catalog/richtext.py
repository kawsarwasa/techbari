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
}
_VOID_TAGS = {"br"}


class _RichTextSanitizer(HTMLParser):
    """Very small allow-list sanitizer for the catalog description editor.

    The editor intentionally supports formatting tags only. Attributes are removed,
    which prevents script/event/style injection while preserving basic formatting.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _ALLOWED_TAGS:
            self.parts.append(f"<{tag}>")

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if tag in _ALLOWED_TAGS:
            self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _ALLOWED_TAGS and tag not in _VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(escape(data))

    def handle_comment(self, data):
        # Comments are intentionally discarded.
        return


def sanitize_rich_html(value):
    if not value:
        return ""
    parser = _RichTextSanitizer()
    parser.feed(str(value))
    parser.close()
    return "".join(parser.parts).strip()


def inline_rich_html(value):
    """Return safe rich HTML that can live inside the legacy paragraph wrapper.

    The storefront currently wraps each description block in a <p>. Convert block
    tags produced by the editor into inline-safe equivalents while keeping bold,
    italic, underline, line breaks and list readability.
    """

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

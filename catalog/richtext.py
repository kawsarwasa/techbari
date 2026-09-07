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
_DROP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed"}


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
            self.parts.append(f"<{tag}>")

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if self.drop_depth or tag in _DROP_CONTENT_TAGS:
            return
        if tag in _ALLOWED_TAGS:
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

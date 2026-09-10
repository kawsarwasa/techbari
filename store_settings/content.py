import re
from html import escape
from html.parser import HTMLParser

from django.utils.html import linebreaks
from django.utils.safestring import mark_safe


ALLOWED_CONTENT_TAGS = {
    "p",
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

_HTML_TAG_RE = re.compile(r"<\s*/?\s*[A-Za-z][^>]*>")


class _ContentPageHTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.div_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "div":
            self.parts.append("<p>")
            self.div_depth += 1
            return
        if tag in ALLOWED_CONTENT_TAGS:
            self.parts.append("<br>" if tag == "br" else f"<{tag}>")

    def handle_startendtag(self, tag, attrs):
        if tag.lower() == "br":
            self.parts.append("<br>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "div" and self.div_depth:
            self.parts.append("</p>")
            self.div_depth -= 1
            return
        if tag in ALLOWED_CONTENT_TAGS and tag != "br":
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(escape(data))

    def handle_comment(self, data):
        return

    def html(self):
        while self.div_depth:
            self.parts.append("</p>")
            self.div_depth -= 1
        return "".join(self.parts)


def contains_html(value):
    return bool(_HTML_TAG_RE.search(value or ""))


def sanitize_content_page_html(value):
    parser = _ContentPageHTMLSanitizer()
    parser.feed(value or "")
    parser.close()
    return parser.html()


def sanitize_content_page_input(value):
    value = value or ""
    if not contains_html(value):
        return value
    return sanitize_content_page_html(value)


def render_content_page_body(value):
    value = value or ""
    if contains_html(value):
        return mark_safe(sanitize_content_page_html(value))
    return mark_safe(linebreaks(value, autoescape=True))

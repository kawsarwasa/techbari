from django.test import SimpleTestCase

from .richtext import sanitize_rich_html


class QuillRichTextSanitizerTests(SimpleTestCase):
    def test_preserves_allowlisted_quill_styles(self):
        value = (
            '<h2 style="text-align:center">Title</h2>'
            '<p><span style="font-size:20px;color:#e60000;background-color:#ffff00">Styled text</span></p>'
        )
        sanitized = sanitize_rich_html(value)
        self.assertIn('<h2 style="text-align:center">Title</h2>', sanitized)
        self.assertIn('font-size:20px', sanitized)
        self.assertIn('color:#e60000', sanitized)
        self.assertIn('background-color:#ffff00', sanitized)

    def test_strips_unsafe_styles_attributes_and_embeds(self):
        value = (
            '<p onclick="bad()" style="position:fixed;text-align:center">Safe</p>'
            '<span style="font-size:99px;color:url(javascript:bad);position:absolute">Text</span>'
            '<script>alert(1)</script><iframe src="https://example.com">bad</iframe>'
        )
        sanitized = sanitize_rich_html(value)
        self.assertIn('<p style="text-align:center">Safe</p>', sanitized)
        self.assertIn('<span>Text</span>', sanitized)
        self.assertNotIn('onclick', sanitized)
        self.assertNotIn('position:', sanitized)
        self.assertNotIn('javascript:', sanitized)
        self.assertNotIn('<script', sanitized)
        self.assertNotIn('<iframe', sanitized)
        self.assertNotIn('alert(1)', sanitized)

    def test_preserves_rgb_color_and_strikethrough(self):
        value = '<p><s><span style="color:rgb(12, 34, 56)">Sale</span></s></p>'
        sanitized = sanitize_rich_html(value)
        self.assertEqual(sanitized, '<p><s><span style="color:rgb(12, 34, 56)">Sale</span></s></p>')

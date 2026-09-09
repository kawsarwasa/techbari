from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, UnidentifiedImageError

from .content import sanitize_content_page_input
from .models import ContentPage, HeroBanner, HomeSection, StoreSettings


MAX_CMS_IMAGE_BYTES = 2 * 1024 * 1024
CMS_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
CMS_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
FAVICON_EXTENSIONS = CMS_IMAGE_EXTENSIONS | {".ico"}
FAVICON_TYPES = CMS_IMAGE_TYPES | {"image/x-icon", "image/vnd.microsoft.icon"}


def validate_cms_image(upload, *, favicon=False):
    if not upload or not isinstance(upload, UploadedFile):
        return upload
    if upload.size > MAX_CMS_IMAGE_BYTES:
        raise ValidationError(f"{upload.name}: image must be 2MB or smaller.")
    extensions = FAVICON_EXTENSIONS if favicon else CMS_IMAGE_EXTENSIONS
    content_types = FAVICON_TYPES if favicon else CMS_IMAGE_TYPES
    if Path(upload.name).suffix.lower() not in extensions:
        raise ValidationError(f"{upload.name}: unsupported image extension.")
    content_type = (getattr(upload, "content_type", "") or "").lower()
    if content_type and content_type not in content_types:
        raise ValidationError(f"{upload.name}: unsupported image content type.")
    try:
        position = upload.tell()
        image = Image.open(upload)
        image.verify()
        upload.seek(position)
    except (UnidentifiedImageError, OSError, ValueError):
        try:
            upload.seek(0)
        except Exception:
            pass
        raise ValidationError(f"{upload.name}: invalid or corrupted image file.")
    return upload


def _style(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            continue
        widget.attrs.setdefault("class", "control")


class StoreSettingsForm(forms.ModelForm):
    class Meta:
        model = StoreSettings
        fields = (
            "store_name", "tagline", "support_phone", "support_hours", "support_email", "business_email", "address",
            "logo", "favicon", "facebook_url", "youtube_url", "instagram_url", "tiktok_url", "whatsapp_number",
            "topbar_delivery_text", "topbar_authentic_text", "topbar_return_text", "footer_about", "copyright_text",
            "currency_code", "currency_symbol", "delivery_inside_dhaka_charge", "delivery_outside_dhaka_charge",
            "free_delivery_threshold", "delivery_inside_days_min", "delivery_inside_days_max",
            "delivery_outside_days_min", "delivery_outside_days_max", "cod_enabled", "guest_checkout_enabled",
            "seo_title", "seo_description", "seo_keywords", "homepage_seo_title", "homepage_seo_description",
        )
        widgets = {"address": forms.Textarea(attrs={"rows": 3}), "footer_about": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

    def clean_logo(self):
        return validate_cms_image(self.cleaned_data.get("logo"))

    def clean_favicon(self):
        return validate_cms_image(self.cleaned_data.get("favicon"), favicon=True)


class HeroBannerForm(forms.ModelForm):
    class Meta:
        model = HeroBanner
        fields = ("eyebrow", "title", "description", "cta_label", "cta_url", "image", "fallback_static", "alt_text", "is_active", "sort_order", "starts_at", "ends_at")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["ends_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        _style(self)

    def clean_cta_url(self):
        value = (self.cleaned_data.get("cta_url") or "").strip()
        if value and not (value.startswith("/") or value.startswith("https://") or value.startswith("http://")):
            raise ValidationError("Use a site-relative path starting with / or an http/https URL.")
        return value

    def clean_image(self):
        return validate_cms_image(self.cleaned_data.get("image"))


class HomeSectionForm(forms.ModelForm):
    class Meta:
        model = HomeSection
        fields = ("title", "sort_order", "is_enabled")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class ContentPageForm(forms.ModelForm):
    class Meta:
        model = ContentPage
        fields = ("title", "body", "seo_title", "seo_description", "is_published")
        widgets = {
            "body": forms.Textarea(attrs={
                "rows": 16,
                "class": "control techbari-editor-source",
                "data-editor-source": "",
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

    def clean_body(self):
        return sanitize_content_page_input(self.cleaned_data.get("body"))

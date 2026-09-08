from django import forms
from django.core.exceptions import ValidationError

from .models import ContentPage, HeroBanner, HomeSection, StoreSettings


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
        widgets = {"body": forms.Textarea(attrs={"rows": 16})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

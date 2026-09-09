from django import forms
from django.core.exceptions import ValidationError

from .models import IntegrationSettings
from .security import validate_outbound_url


class IntegrationSettingsForm(forms.ModelForm):
    class Meta:
        model = IntegrationSettings
        fields = [
            "email_enabled", "sms_enabled", "whatsapp_enabled",
            "notify_order_events", "notify_payment_events", "notify_low_stock", "notify_shipping_events",
            "admin_email", "admin_phone", "sms_webhook_url", "whatsapp_webhook_url",
            "meta_pixel_enabled", "meta_pixel_id", "meta_capi_enabled",
            "ga4_enabled", "ga4_measurement_id", "ga4_server_enabled",
            "courier_api_enabled",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            field.widget.attrs.setdefault("class", "control")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("sms_enabled") and not cleaned.get("sms_webhook_url"):
            self.add_error("sms_webhook_url", "SMS webhook URL is required when SMS is enabled.")
        if cleaned.get("whatsapp_enabled") and not cleaned.get("whatsapp_webhook_url"):
            self.add_error("whatsapp_webhook_url", "WhatsApp webhook URL is required when WhatsApp is enabled.")
        for field_name in ("sms_webhook_url", "whatsapp_webhook_url"):
            value = cleaned.get(field_name)
            if value:
                try:
                    validate_outbound_url(value, resolve=False)
                except ValidationError as exc:
                    self.add_error(field_name, exc)
        if (cleaned.get("meta_pixel_enabled") or cleaned.get("meta_capi_enabled")) and not cleaned.get("meta_pixel_id"):
            self.add_error("meta_pixel_id", "Meta Pixel ID is required when Meta tracking is enabled.")
        if (cleaned.get("ga4_enabled") or cleaned.get("ga4_server_enabled")) and not cleaned.get("ga4_measurement_id"):
            self.add_error("ga4_measurement_id", "GA4 Measurement ID is required when GA4 is enabled.")
        return cleaned

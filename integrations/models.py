from django.conf import settings
from django.db import models
from django.utils import timezone


class IntegrationSettings(models.Model):
    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)

    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    whatsapp_enabled = models.BooleanField(default=False)

    notify_order_events = models.BooleanField(default=True)
    notify_payment_events = models.BooleanField(default=True)
    notify_low_stock = models.BooleanField(default=True)
    notify_shipping_events = models.BooleanField(default=True)

    admin_email = models.EmailField(blank=True)
    admin_phone = models.CharField(max_length=40, blank=True)
    sms_webhook_url = models.URLField(blank=True)
    whatsapp_webhook_url = models.URLField(blank=True)

    meta_pixel_enabled = models.BooleanField(default=False)
    meta_pixel_id = models.CharField(max_length=80, blank=True)
    meta_capi_enabled = models.BooleanField(default=False)

    ga4_enabled = models.BooleanField(default=False)
    ga4_measurement_id = models.CharField(max_length=80, blank=True)
    ga4_server_enabled = models.BooleanField(default=False)

    courier_api_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "integration settings"

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        return super().save(*args, **kwargs)

    def __str__(self):
        return "TechBari integrations"


class Notification(models.Model):
    class Kind(models.TextChoices):
        ORDER = "order", "Order"
        PAYMENT = "payment", "Payment"
        STOCK = "stock", "Stock"
        SHIPPING = "shipping", "Shipping"
        INTEGRATION = "integration", "Integration"

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        DANGER = "danger", "Danger"

    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.INFO if hasattr(Kind, "INFO") else Kind.ORDER)
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.INFO)
    title = models.CharField(max_length=180)
    message = models.CharField(max_length=500)
    link = models.CharField(max_length=500, blank=True)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.CharField(max_length=100, blank=True)
    dedupe_key = models.CharField(max_length=220, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("kind", "created_at"), name="int_notif_kind_time_idx"),
            models.Index(fields=("created_at",), name="int_notif_time_idx"),
        ]

    def __str__(self):
        return self.title


class NotificationRead(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_reads")
    read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("notification", "user"), name="uniq_int_notification_read")]
        indexes = [models.Index(fields=("user", "read_at"), name="int_notif_read_user_idx")]


class OutboundMessage(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        WHATSAPP = "whatsapp", "WhatsApp"
        META_CAPI = "meta_capi", "Meta CAPI"
        GA4 = "ga4", "Google Analytics 4"
        COURIER = "courier", "Courier API"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    channel = models.CharField(max_length=24, choices=Channel.choices)
    event_type = models.CharField(max_length=80)
    recipient = models.CharField(max_length=500, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=220, unique=True)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("status", "available_at", "id")
        indexes = [
            models.Index(fields=("status", "available_at"), name="int_outbox_status_idx"),
            models.Index(fields=("channel", "created_at"), name="int_outbox_channel_idx"),
            models.Index(fields=("reference_type", "reference_id"), name="int_outbox_ref_idx"),
        ]

    def __str__(self):
        return f"{self.get_channel_display()} / {self.event_type} / {self.status}"


class CourierWebhookReceipt(models.Model):
    provider_code = models.CharField(max_length=64)
    digest = models.CharField(max_length=64, unique=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-received_at", "-id")
        indexes = [models.Index(fields=("provider_code", "received_at"), name="int_hook_provider_time_idx")]

    def __str__(self):
        return f"{self.provider_code}:{self.digest[:12]}"

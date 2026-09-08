from decimal import Decimal
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from promotions.forms import CampaignForm, CouponForm, FlashSaleForm
from promotions.models import Campaign, CampaignEvent, Coupon, CouponRedemption, FlashSale
from .context import page_context

ZERO = Decimal("0.00")
NOTICE_TEXT = {"coupon-saved": "Coupon saved successfully.", "coupon-toggled": "Coupon status updated.", "campaign-saved": "Campaign saved successfully.", "campaign-toggled": "Campaign status updated.", "flash-saved": "Flash Sale saved successfully.", "flash-toggled": "Flash Sale status updated.", "featured-toggled": "Featured product status updated."}


def _message(exc): return " ".join(str(value) for value in exc.messages) if hasattr(exc, "messages") else str(exc)

def _redirect(route_name, *, notice="", error="", params=None):
    url = reverse(route_name); query = dict(params or {})
    if notice: query["notice"] = notice
    if error: query["error"] = error
    return redirect(url + ("?" + urlencode(query) if query else ""))

def _base_context(request, page_name="marketing"):
    context = page_context(page_name); context.update(promotion_database=True, promotion_notice=NOTICE_TEXT.get(request.GET.get("notice", ""), ""), promotion_error=request.GET.get("error", "")); return context


def marketing(request):
    now = timezone.now(); edit_campaign_id = request.GET.get("edit_campaign", ""); edit_flash_id = request.GET.get("edit_flash", "")
    campaign_instance = Campaign.objects.filter(pk=int(edit_campaign_id)).first() if edit_campaign_id.isdigit() else None
    flash_instance = FlashSale.objects.filter(pk=int(edit_flash_id)).first() if edit_flash_id.isdigit() else None
    campaign_form = CampaignForm(instance=campaign_instance); flash_form = FlashSaleForm(instance=flash_instance); error = ""
    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "save-campaign":
                campaign_id = request.POST.get("campaign_id", ""); instance = Campaign.objects.filter(pk=int(campaign_id)).first() if campaign_id.isdigit() else None; campaign_form = CampaignForm(request.POST, instance=instance)
                if campaign_form.is_valid(): campaign = campaign_form.save(commit=False); campaign.full_clean(); campaign.save(); return _redirect("backoffice:marketing", notice="campaign-saved")
                error = "Please correct the campaign fields."
            elif action == "toggle-campaign":
                campaign = get_object_or_404(Campaign, pk=request.POST.get("campaign_id")); campaign.is_active = not campaign.is_active; campaign.save(update_fields=["is_active", "updated_at"]); return _redirect("backoffice:marketing", notice="campaign-toggled")
            elif action == "save-flash":
                flash_id = request.POST.get("flash_id", ""); instance = FlashSale.objects.filter(pk=int(flash_id)).first() if flash_id.isdigit() else None; flash_form = FlashSaleForm(request.POST, instance=instance)
                if flash_form.is_valid(): flash_sale = flash_form.save(commit=False); flash_sale.full_clean(); flash_sale.save(); flash_form.save_m2m(); return _redirect("backoffice:marketing", notice="flash-saved")
                error = "Please correct the Flash Sale fields."
            elif action == "toggle-flash":
                flash_sale = get_object_or_404(FlashSale, pk=request.POST.get("flash_id")); flash_sale.is_active = not flash_sale.is_active; flash_sale.save(update_fields=["is_active", "updated_at"]); return _redirect("backoffice:marketing", notice="flash-toggled")
            elif action == "toggle-featured":
                product = get_object_or_404(Product, pk=request.POST.get("product_id")); product.is_featured = not product.is_featured; product.save(update_fields=["is_featured", "updated_at"]); return _redirect("backoffice:marketing", notice="featured-toggled")
            else: return _redirect("backoffice:marketing", error="Unknown marketing action.")
        except (ValidationError, ValueError) as exc: error = _message(exc)
    live_coupon_count = sum(1 for coupon in Coupon.objects.filter(is_active=True, starts_at__lte=now, ends_at__gte=now) if coupon.is_live)
    conversion_total = CampaignEvent.objects.filter(event_type=CampaignEvent.EventType.CONVERSION).aggregate(total=Sum("amount"))["total"] or ZERO
    savings_total = CouponRedemption.objects.aggregate(total=Sum("discount_amount"))["total"] or ZERO
    context = _base_context(request); context.update(campaign_rows=Campaign.objects.all()[:20], flash_rows=FlashSale.objects.prefetch_related("products").all()[:20], recent_campaign_events=CampaignEvent.objects.select_related("campaign", "order", "coupon").all()[:20], campaign_form=campaign_form, flash_form=flash_form, editing_campaign=campaign_instance, editing_flash=flash_instance, promotion_error=error or context.get("promotion_error", ""), promotion_kpis={"live_coupons": live_coupon_count, "live_flash_sales": FlashSale.objects.filter(is_active=True, starts_at__lte=now, ends_at__gte=now).count(), "live_campaigns": Campaign.objects.filter(is_active=True, starts_at__lte=now, ends_at__gte=now).count(), "conversions": CampaignEvent.objects.filter(event_type=CampaignEvent.EventType.CONVERSION).count(), "conversion_revenue": conversion_total, "coupon_savings": savings_total, "featured_products": Product.objects.filter(is_featured=True).count()}, featured_products=Product.objects.select_related("category", "brand").order_by("-is_featured", "name")[:50])
    return render(request, "backoffice/pages/marketing/marketing.html", context)


def coupons(request):
    if request.method == "POST":
        if request.POST.get("action", "") != "toggle": return _redirect("backoffice:coupons", error="Unknown coupon action.")
        coupon = get_object_or_404(Coupon, pk=request.POST.get("coupon_id")); coupon.is_active = not coupon.is_active; coupon.save(update_fields=["is_active", "updated_at"]); return _redirect("backoffice:coupons", notice="coupon-toggled")
    query = (request.GET.get("q") or "").strip(); status = (request.GET.get("status") or "").strip(); qs = Coupon.objects.select_related("campaign").prefetch_related("products", "categories")
    if query: qs = qs.filter(Q(code__icontains=query) | Q(name__icontains=query) | Q(campaign__name__icontains=query))
    now = timezone.now()
    if status == "active": qs = qs.filter(is_active=True, starts_at__lte=now, ends_at__gte=now)
    elif status == "inactive": qs = qs.filter(is_active=False)
    elif status == "expired": qs = qs.filter(ends_at__lt=now)
    context = _base_context(request, "coupons"); context.update(coupon_rows=qs, coupon_query=query, coupon_status=status, coupon_kpis={"total": Coupon.objects.count(), "active": sum(1 for coupon in Coupon.objects.all() if coupon.is_live), "redemptions": CouponRedemption.objects.count(), "discount_total": CouponRedemption.objects.aggregate(total=Sum("discount_amount"))["total"] or ZERO}); return render(request, "backoffice/pages/coupons/coupons.html", context)


def coupon_add(request):
    edit_id = request.GET.get("edit", "") if request.method == "GET" else request.POST.get("coupon_id", ""); instance = Coupon.objects.filter(pk=int(edit_id)).first() if str(edit_id).isdigit() else None; form = CouponForm(request.POST or None, instance=instance); error = ""
    if request.method == "POST":
        if form.is_valid():
            try: coupon = form.save(commit=False); coupon.full_clean(); coupon.save(); form.save_m2m(); return _redirect("backoffice:coupons", notice="coupon-saved")
            except ValidationError as exc: error = _message(exc)
        else: error = "Please correct the coupon fields."
    context = _base_context(request, "coupon_add"); context.update(coupon_form=form, editing_coupon=instance, promotion_error=error or context.get("promotion_error", "")); return render(request, "backoffice/pages/coupons/coupon_add.html", context)

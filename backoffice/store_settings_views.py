from django.contrib import messages
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from store_settings.forms import ContentPageForm, HeroBannerForm, HomeSectionForm, StoreSettingsForm
from store_settings.models import ContentPage, HeroBanner, HomeSection, StoreSettings
from .context import page_context


def _context(**extra):
    context = page_context("settings")
    context.update(extra)
    return context


def settings_view(request):
    store = StoreSettings.get_solo()
    if request.method == "POST":
        form = StoreSettingsForm(request.POST, request.FILES, instance=store)
        if form.is_valid():
            form.save()
            messages.success(request, "Store settings saved successfully.")
            return redirect("backoffice:settings")
    else:
        form = StoreSettingsForm(instance=store)
    return render(request, "backoffice/pages/settings/settings.html", _context(
        settings_form=form,
        store=store,
        banner_count=HeroBanner.objects.count(),
        live_banner_count=sum(1 for banner in HeroBanner.objects.all() if banner.is_live),
        section_count=HomeSection.objects.count(),
        page_count=ContentPage.objects.count(),
    ))


def banners(request):
    rows = HeroBanner.objects.all()
    return render(request, "backoffice/pages/settings/banners.html", _context(banners=rows))


def banner_form(request, banner_id=None):
    banner = get_object_or_404(HeroBanner, pk=banner_id) if banner_id else None
    if request.method == "POST":
        form = HeroBannerForm(request.POST, request.FILES, instance=banner)
        if form.is_valid():
            saved = form.save()
            messages.success(request, f"Hero banner {'updated' if banner else 'created'}: {saved.title}")
            return redirect("backoffice:cms_banners")
    else:
        form = HeroBannerForm(instance=banner)
    return render(request, "backoffice/pages/settings/banner_form.html", _context(banner_form=form, banner=banner))


def banner_delete(request, banner_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    banner = get_object_or_404(HeroBanner, pk=banner_id)
    title = banner.title
    banner.delete()
    messages.success(request, f"Hero banner deleted: {title}")
    return redirect("backoffice:cms_banners")


def homepage_sections(request):
    rows = HomeSection.objects.order_by("sort_order", "id")
    return render(request, "backoffice/pages/settings/homepage_sections.html", _context(sections=rows))


def homepage_section_update(request, section_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    section = get_object_or_404(HomeSection, pk=section_id)
    form = HomeSectionForm(request.POST, instance=section)
    if form.is_valid():
        form.save()
        messages.success(request, f"Homepage section updated: {section.get_key_display()}")
    else:
        messages.error(request, "Could not update the homepage section.")
    return redirect("backoffice:cms_homepage_sections")


def content_pages(request):
    rows = ContentPage.objects.order_by("title")
    return render(request, "backoffice/pages/settings/content_pages.html", _context(content_pages=rows))


def content_page_edit(request, page_id):
    page = get_object_or_404(ContentPage, pk=page_id)
    if request.method == "POST":
        form = ContentPageForm(request.POST, instance=page)
        if form.is_valid():
            form.save()
            messages.success(request, f"Content page updated: {page.title}")
            return redirect("backoffice:cms_content_pages")
    else:
        form = ContentPageForm(instance=page)
    return render(request, "backoffice/pages/settings/content_page_form.html", _context(content_page=page, content_page_form=form))

from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.forms.models import model_to_dict
from django.test import TestCase, override_settings
from django.urls import reverse

from staff_access.permissions import sync_system_roles
from .forms import ContentPageForm, StoreSettingsForm
from .models import ContentPage, HeroBanner, HomeSection, StoreSettings
from .services import serialize_hero_banner, shipping_charge_for_subtotal


class StoreSettingsCMSTests(TestCase):
    def settings_post_data(self, store):
        data = model_to_dict(store, fields=StoreSettingsForm.Meta.fields)
        data.pop("logo", None)
        data.pop("favicon", None)
        for key, value in list(data.items()):
            if isinstance(value, bool):
                if value:
                    data[key] = "on"
                else:
                    data.pop(key)
        return data

    def test_seeded_cms_defaults_exist(self):
        store = StoreSettings.get_solo()
        self.assertEqual(store.store_name, "TechBari")
        self.assertEqual(HomeSection.objects.count(), 4)
        self.assertGreaterEqual(HeroBanner.objects.count(), 3)
        self.assertTrue(ContentPage.objects.filter(slug="privacy-policy", is_published=True).exists())
        self.assertTrue(ContentPage.objects.filter(slug="return-refund-policy", is_published=True).exists())

    def test_store_settings_dashboard_updates_real_database(self):
        store = StoreSettings.get_solo()
        data = self.settings_post_data(store)
        data.update({
            "store_name": "TechBari QA",
            "support_phone": "09600-000000",
            "delivery_inside_dhaka_charge": "75.00",
            "free_delivery_threshold": "1000.00",
            "homepage_seo_title": "QA Electronics Store",
        })
        response = self.client.post(reverse("backoffice:settings"), data)
        self.assertEqual(response.status_code, 302)
        store.refresh_from_db()
        self.assertEqual(store.store_name, "TechBari QA")
        self.assertEqual(store.delivery_inside_dhaka_charge, Decimal("75.00"))
        self.assertEqual(store.free_delivery_threshold, Decimal("1000.00"))

    def test_banner_crud_and_safe_serialization(self):
        response = self.client.post(reverse("backoffice:cms_banner_add"), {
            "eyebrow": "QA",
            "title": "<script>alert(1)</script>\nSafe headline",
            "description": "Line one\nLine two",
            "cta_label": "Shop QA",
            "cta_url": "/products/",
            "fallback_static": "store/images/hero-audio.webp",
            "alt_text": "QA banner",
            "sort_order": "1",
            "is_active": "on",
            "starts_at": "",
            "ends_at": "",
        })
        self.assertEqual(response.status_code, 302)
        banner = HeroBanner.objects.get(eyebrow="QA")
        payload = serialize_hero_banner(banner)
        self.assertIn("&lt;script&gt;", payload["title"])
        self.assertNotIn("<script>", payload["title"])
        self.assertIn("<br>", payload["title"])

        delete = self.client.post(reverse("backoffice:cms_banner_delete", args=[banner.pk]))
        self.assertEqual(delete.status_code, 302)
        self.assertFalse(HeroBanner.objects.filter(pk=banner.pk).exists())

    def test_homepage_section_visibility_and_order_are_database_backed(self):
        hero = HomeSection.objects.get(key=HomeSection.Key.HERO)
        hero.sort_order = 90
        hero.is_enabled = False
        hero.save()
        response = self.client.get(reverse("storefront:home"))
        self.assertEqual(response.status_code, 200)
        sections = response.context["homepage_sections"]
        self.assertEqual(sections[-1].key, HomeSection.Key.HERO)
        self.assertNotContains(response, 'id="homeHero"')

    def test_policy_page_publication_and_seo(self):
        page = ContentPage.objects.get(slug="privacy-policy")
        page.title = "QA Privacy"
        page.seo_title = "QA Privacy SEO"
        page.seo_description = "QA privacy description"
        page.save()
        response = self.client.get(reverse("storefront:privacy_policy"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "QA Privacy")
        self.assertContains(response, "QA Privacy SEO")
        self.assertContains(response, 'meta name="description" content="QA privacy description"', html=False)
        page.is_published = False
        page.save()
        self.assertEqual(self.client.get(reverse("storefront:privacy_policy")).status_code, 404)

    def test_content_page_form_sanitizes_rich_html_and_storefront_renders_formatting(self):
        page = ContentPage.objects.get(slug="privacy-policy")
        form = ContentPageForm(data={
            "title": "Privacy Policy",
            "body": '<h2>Privacy Matters</h2><p onclick="alert(1)">Safe <strong>content</strong>.</p><script>alert(1)</script>',
            "seo_title": "Privacy Policy | TechBari",
            "seo_description": "Safe privacy page",
            "is_published": "on",
        }, instance=page)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertIn("<h2>Privacy Matters</h2>", saved.body)
        self.assertIn("<strong>content</strong>", saved.body)
        self.assertNotIn("onclick", saved.body)
        self.assertNotIn("<script", saved.body)

        response = self.client.get(reverse("storefront:privacy_policy"))
        self.assertContains(response, "<h2>Privacy Matters</h2>", html=False)
        self.assertContains(response, "<strong>content</strong>", html=False)
        self.assertNotContains(response, "<script", html=False)

    def test_content_page_browser_div_blocks_are_normalized_to_paragraphs(self):
        page = ContentPage.objects.get(slug="privacy-policy")
        form = ContentPageForm(data={
            "title": page.title,
            "body": "<div>First block</div><div><strong>Second block</strong></div>",
            "seo_title": page.seo_title,
            "seo_description": page.seo_description,
            "is_published": "on",
        }, instance=page)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertIn("<p>First block</p>", saved.body)
        self.assertIn("<p><strong>Second block</strong></p>", saved.body)
        self.assertNotIn("<div", saved.body)

    def test_content_page_plain_text_remains_linebreak_formatted(self):
        page = ContentPage.objects.get(slug="shipping-policy")
        page.body = "First paragraph\n\nSecond paragraph"
        page.save()
        response = self.client.get(reverse("storefront:shipping_policy"))
        self.assertContains(response, "<p>First paragraph</p>", html=False)
        self.assertContains(response, "<p>Second paragraph</p>", html=False)

    def test_homepage_branding_and_seo_use_store_settings(self):
        store = StoreSettings.get_solo()
        store.store_name = "CMS Store"
        store.support_phone = "01900000000"
        store.homepage_seo_title = "CMS Home SEO"
        store.homepage_seo_description = "CMS home description"
        store.save()
        response = self.client.get(reverse("storefront:home"))
        self.assertContains(response, "CMS Store")
        self.assertContains(response, "01900000000")
        self.assertContains(response, "CMS Home SEO")

    def test_delivery_service_uses_configured_charges_and_free_threshold(self):
        store = StoreSettings.get_solo()
        store.delivery_inside_dhaka_charge = Decimal("80.00")
        store.delivery_outside_dhaka_charge = Decimal("150.00")
        store.free_delivery_threshold = Decimal("1000.00")
        store.save()
        self.assertEqual(shipping_charge_for_subtotal(Decimal("500.00"), "inside"), Decimal("80.00"))
        self.assertEqual(shipping_charge_for_subtotal(Decimal("500.00"), "outside"), Decimal("150.00"))
        self.assertEqual(shipping_charge_for_subtotal(Decimal("1000.00"), "inside"), Decimal("0.00"))
        self.assertIsNone(shipping_charge_for_subtotal(Decimal("100.00"), "invalid"))


@override_settings(STAFF_AUTH_ENABLED=True)
class StoreSettingsPermissionTests(TestCase):
    def setUp(self):
        sync_system_roles()
        self.password = "StrongPass123!"

    def make_user(self, username, role):
        user = User.objects.create_user(username=username, password=self.password, is_staff=True)
        user.groups.add(Group.objects.get(name=role))
        return user

    def test_cashier_is_denied_but_manager_can_manage_store_settings(self):
        cashier = self.make_user("cmscashier", "Cashier")
        self.client.force_login(cashier)
        self.assertEqual(self.client.get(reverse("backoffice:settings")).status_code, 403)
        self.assertEqual(self.client.get(reverse("backoffice:cms_banners")).status_code, 403)

        manager = self.make_user("cmsmanager", "Manager")
        self.client.force_login(manager)
        self.assertEqual(self.client.get(reverse("backoffice:settings")).status_code, 200)
        self.assertEqual(self.client.get(reverse("backoffice:cms_content_pages")).status_code, 200)

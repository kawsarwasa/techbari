from django.db import migrations


def enable_featured_home_section(apps, schema_editor):
    HomeSection = apps.get_model("store_settings", "HomeSection")
    section, _ = HomeSection.objects.get_or_create(
        key="featured",
        defaults={
            "title": "Featured Products",
            "sort_order": 30,
            "is_enabled": True,
        },
    )
    updates = []
    if not section.is_enabled:
        section.is_enabled = True
        updates.append("is_enabled")
    if not section.title:
        section.title = "Featured Products"
        updates.append("title")
    if updates:
        section.save(update_fields=updates)


class Migration(migrations.Migration):
    dependencies = [
        ("store_settings", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(enable_featured_home_section, migrations.RunPython.noop),
    ]

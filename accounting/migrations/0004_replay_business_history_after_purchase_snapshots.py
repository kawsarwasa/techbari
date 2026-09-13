from django.db import migrations


def replay_business_history(apps, schema_editor):
    # accounting.services uses source_key-based idempotency, so this safely fills
    # anything skipped by the guarded legacy 0002 migration without duplicating
    # journals on databases where 0002 already completed in an earlier release.
    from accounting.services import backfill_accounting_history

    backfill_accounting_history(actor="variant hardening migration")


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0003_expense_source"),
        ("catalog", "0003_product_variant_options"),
        ("purchasing", "0003_purchase_item_snapshots"),
    ]

    operations = [
        migrations.RunPython(replay_business_history, migrations.RunPython.noop),
    ]

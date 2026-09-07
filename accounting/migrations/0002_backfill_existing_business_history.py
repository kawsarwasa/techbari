from django.db import migrations


def backfill_existing_history(apps, schema_editor):
    # The accounting service is intentionally idempotent through source_key, so this
    # migration can safely translate all existing v1.x operational history once the
    # accounting tables and seeded system accounts exist.
    from accounting.services import backfill_accounting_history

    backfill_accounting_history(actor="v2.0.0 migration")


class Migration(migrations.Migration):
    dependencies = [("accounting", "0001_initial")]

    operations = [migrations.RunPython(backfill_existing_history, migrations.RunPython.noop)]

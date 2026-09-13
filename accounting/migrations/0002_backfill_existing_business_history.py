from django.db import migrations


REQUIRED_LATE_PURCHASE_COLUMNS = {
    "product_snapshot",
    "variant_snapshot",
    "sku_snapshot",
}


def _purchase_item_schema_is_current(schema_editor):
    """Return True only when the live purchasing model matches the DB schema.

    This legacy migration calls the current accounting service. Newer releases may
    add concrete fields to purchasing models after this migration's historical
    point. On a fresh install those live-model fields do not exist yet, so querying
    through the current service would fail before the later purchasing migration
    can create them.
    """
    connection = schema_editor.connection
    table_name = "purchasing_purchaseorderitem"
    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }
    return REQUIRED_LATE_PURCHASE_COLUMNS.issubset(columns)


def backfill_existing_history(apps, schema_editor):
    # Existing installations that already applied this migration remain untouched.
    # On a fresh install with newer purchasing fields, defer the live-service
    # backfill until accounting.0004, after the purchasing snapshot migration.
    if not _purchase_item_schema_is_current(schema_editor):
        return

    # The accounting service is intentionally idempotent through source_key, so this
    # migration can safely translate all existing v1.x operational history once the
    # accounting tables and seeded system accounts exist.
    from accounting.services import backfill_accounting_history

    backfill_accounting_history(actor="v2.0.0 migration")


class Migration(migrations.Migration):
    dependencies = [("accounting", "0001_initial")]

    operations = [migrations.RunPython(backfill_existing_history, migrations.RunPython.noop)]

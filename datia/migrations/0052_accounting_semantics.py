from django.db import migrations


def apply_semantics(apps, schema_editor):
    from datia.services.accounting_semantics import apply_accounting_semantics
    apply_accounting_semantics()


class Migration(migrations.Migration):

    dependencies = [
        ("datia", "0051_globalconfig_platform"),
    ]

    operations = [
        migrations.RunPython(apply_semantics, migrations.RunPython.noop),
    ]

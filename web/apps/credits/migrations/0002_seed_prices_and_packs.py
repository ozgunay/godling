"""The prices the screen showed (ADR-011; the meteor at 300, the user's choice) and three credit packs at 5 cents a
credit, cheaper in bulk. The admin changes them from here on."""
from django.db import migrations

POWERS = [("Stone", "Stone", 4), ("Log", "Log", 4), ("Regrow", "Regrow a palm", 6), ("Lightning", "Lightning", 40),
          ("Meteor", "Meteor", 300), ("Earthquake", "Earthquake", 500)]
PACKS = [("handful", "A handful", 100, 500), ("bag", "A bag", 320, 1500), ("chest", "A chest", 1100, 5000)]


def seed(apps, schema_editor):
    Power = apps.get_model("credits", "Power")
    CreditPack = apps.get_model("credits", "CreditPack")
    for sort, (key, label, price) in enumerate(POWERS):
        Power.objects.get_or_create(key=key, defaults={"label": label, "price": price, "sort": sort})
    for sort, (key, name, credits, cents) in enumerate(PACKS):
        CreditPack.objects.get_or_create(key=key, defaults={"name": name, "credits": credits, "price_cents": cents,
                                                            "sort": sort})


class Migration(migrations.Migration):
    dependencies = [("credits", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

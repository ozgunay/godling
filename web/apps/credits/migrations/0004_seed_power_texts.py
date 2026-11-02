"""Each power's words as the screen had them in code (world/viewer/viewer.js POWERS), now on its row."""
from django.db import migrations

TEXTS = {
    "Stone": ("Gift", False, "dropped a stone", "from the sky",
              "A stone block drops where you aim. Aimed at Godling, it lands at its feet; it never lands on its walls.", ""),
    "Log": ("Gift", False, "dropped a log", "from the sky",
            "A log beam drops where you aim. Aimed at Godling, it lands at its feet; it never lands on its walls.", ""),
    "Regrow": ("Gift", False, "regrew a palm", "from its stump", "The stump nearest your aim grows back at once.", ""),
    "Lightning": ("Wonder", False, "called lightning", "a palm comes down",
                  "Strikes the palm nearest your aim and fells it into two logs. Only palms well away from Godling "
                  "and its walls.", ""),
    "Meteor": ("Disaster", True, "called a meteor", "it blasts in 40 s",
               "A shadow spreads where you aim; 40 s later a stone blasts there, whatever stands in it: Godling, its "
               "walls, palms. It leaves a crater.",
               "The only power that can hit Godling or its walls · one a minute · never while Godling is weak"),
    "Earthquake": ("Disaster", True, "shook the island", "the ground rumbles",
                   "The ground rumbles, then shakes for 20 s. Loose pieces fall, fastened ones hold. Godling braces; "
                   "it is never hurt.", "One every 10 minutes, never while Godling is weak"),
}


def seed(apps, schema_editor):
    Power = apps.get_model("credits", "Power")
    for key, (kind, harms, did, after, description, rule) in TEXTS.items():
        Power.objects.filter(key=key).update(kind=kind, harms=harms, did=did, after=after, description=description,
                                             rule=rule)


class Migration(migrations.Migration):
    dependencies = [("credits", "0003_power_after_power_description_power_did_power_harms_and_more")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

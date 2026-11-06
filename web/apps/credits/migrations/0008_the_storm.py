"""The Storm takes Lightning's place on the hotbar (ADR-023, the user's choice on 2026-11-06): three aimed strikes in a
storm called down, which can leave Godling with half a heart, so it is priced as a disaster. Lightning stays a power
the world knows (storms of its own still strike palms), switched off here. A power call carries the storm's spots."""
from django.db import migrations, models

STORM = {"label": "Storm", "price": 400, "kind": "Disaster", "harms": True,
         "description": "Pick three spots: 30 s later a storm breaks and lightning strikes each, in its own time. A "
                        "strike on Godling leaves it with half a heart, burned; close by it hurts. A palm comes down as "
                        "two logs; a roof over Godling takes the strike. It never kills.",
         "rule": "One every 30 minutes · never while Godling is weak", "did": "called a storm",
         "after": "it breaks in 30 s"}


def seed(apps, schema_editor):
    Power = apps.get_model("credits", "Power")
    lightning = Power.objects.filter(key="Lightning").first()
    Power.objects.get_or_create(key="Storm", defaults={**STORM, "sort": lightning.sort if lightning else 3})
    Power.objects.filter(key="Lightning").update(enabled=False)


def unseed(apps, schema_editor):
    Power = apps.get_model("credits", "Power")
    Power.objects.filter(key="Storm").delete()
    Power.objects.filter(key="Lightning").update(enabled=True)


class Migration(migrations.Migration):
    dependencies = [("credits", "0007_welcome_once_per_inbox")]
    operations = [
        migrations.AddField(
            model_name="powercall",
            name="spots",
            field=models.JSONField(blank=True, default=list,
                                   help_text="A storm's strikes: up to three [x, z] (ADR-023)."),
        ),
        migrations.RunPython(seed, unseed),
    ]

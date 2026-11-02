from django.db import migrations, models


def fill(apps, schema_editor):
    from apps.users.validators import canonical_email

    User = apps.get_model("users", "User")
    for user in User.objects.only("pk", "email").iterator():
        User.objects.filter(pk=user.pk).update(email_key=canonical_email(user.email))


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_viewer_pace'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_key',
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=254),
        ),
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]

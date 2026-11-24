from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0007_seed_email_verification_template"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationdispatch",
            name="bcc_recipients",
            field=models.JSONField(blank=True, default=list),
        ),
    ]

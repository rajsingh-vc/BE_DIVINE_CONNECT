# Generated for the sequential public volunteer ID feature (vol_1, vol_2, ...)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('volunteers', '0002_rename_volunteers__volunte_5b6b6a_idx_volunteers__volunte_b51d6f_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='volunteer',
            name='public_id',
            field=models.CharField(default=None, editable=False, max_length=20, null=True, unique=True, blank=True),
        ),
        migrations.CreateModel(
            name='VolunteerIdSequence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_number', models.PositiveIntegerField(default=0)),
            ],
        ),
    ]
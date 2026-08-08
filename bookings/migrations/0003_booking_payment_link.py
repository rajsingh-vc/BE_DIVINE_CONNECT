import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0002_bill'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='payment_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='booking',
            name='bill',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='booking', to='bookings.bill'),
        ),
    ]
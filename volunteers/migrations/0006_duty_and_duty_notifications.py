import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('volunteers', '0005_notification_related_incident_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Duty',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('duty_code', models.CharField(editable=False, max_length=20, unique=True)),
                ('title', models.CharField(max_length=200)),
                ('instructions', models.TextField(blank=True, default='')),
                ('location', models.CharField(blank=True, default='', max_length=200)),
                ('duty_date', models.DateField(default=django.utils.timezone.localdate)),
                ('time', models.TimeField(blank=True, null=True)),
                ('priority', models.CharField(choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High')], default='normal', max_length=10)),
                ('status', models.CharField(choices=[('assigned', 'Assigned'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('help_requested', 'Help Requested')], default='assigned', max_length=20)),
                ('help_note', models.CharField(blank=True, default='', max_length=300)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_duties', to=settings.AUTH_USER_MODEL)),
                ('volunteer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='duties', to='volunteers.volunteer')),
            ],
            options={'ordering': ['duty_date', 'time', '-priority']},
        ),
        migrations.AddField(
            model_name='notification',
            name='related_duty',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='volunteers.duty'),
        ),
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.CharField(choices=[
                ('volunteer_approval_required', 'Volunteer Approval Required'),
                ('new_volunteer_application', 'New Volunteer Application'),
                ('status_update', 'Status Update'),
                ('announcement_urgent', 'Urgent Announcement'),
                ('announcement_important', 'Important Announcement'),
                ('incident_reported', 'New Incident Reported'),
                ('incident_response', 'Incident Response'),
                ('duty_assigned', 'Duty Assigned'),
                ('duty_completed', 'Duty Completed'),
                ('duty_help_requested', 'Duty Help/Swap Requested'),
                ('duty_status_update', 'Duty Status Update'),
            ], max_length=40),
        ),
        migrations.AddIndex(
            model_name='duty',
            index=models.Index(fields=['duty_code'], name='volunteers_duty_co_idx'),
        ),
        migrations.AddIndex(
            model_name='duty',
            index=models.Index(fields=['status'], name='volunteers_duty_status_idx'),
        ),
        migrations.AddIndex(
            model_name='duty',
            index=models.Index(fields=['volunteer', 'duty_date'], name='volunteers_duty_vol_date_idx'),
        ),
    ]
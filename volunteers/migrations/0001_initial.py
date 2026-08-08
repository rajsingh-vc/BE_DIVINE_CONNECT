import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import volunteers.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("devotees", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Volunteer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("volunteer_code", models.CharField(editable=False, max_length=20, unique=True)),
                ("name", models.CharField(max_length=150)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(max_length=20)),
                ("profile_photo", models.ImageField(blank=True, null=True, upload_to=volunteers.models.volunteer_photo_path)),
                ("is_volunteer", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending_volunteer_approval", "Pending Volunteer Approval"),
                            ("volunteer_approved", "Volunteer Approved"),
                            ("volunteer_rejected", "Volunteer Rejected"),
                            ("admin_approved", "Admin Approved"),
                            ("admin_rejected", "Admin Rejected"),
                            ("auto_rejected", "Auto Rejected"),
                        ],
                        default="pending_volunteer_approval",
                        max_length=30,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_volunteers", to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "devotee",
                    models.OneToOneField(
                        blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                        related_name="volunteer_profile", to="devotees.devotee",
                    ),
                ),
                (
                    "reference_volunteer",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                        related_name="referred_volunteers", to="volunteers.volunteer",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                        related_name="volunteer_profile_v2", to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="volunteer",
            index=models.Index(fields=["volunteer_code"], name="volunteers__volunte_5b6b6a_idx"),
        ),
        migrations.AddIndex(
            model_name="volunteer",
            index=models.Index(fields=["status"], name="volunteers__status_7c2f11_idx"),
        ),
        migrations.AddIndex(
            model_name="volunteer",
            index=models.Index(fields=["is_volunteer"], name="volunteers__is_volu_3d9a02_idx"),
        ),
        migrations.CreateModel(
            name="Verification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("aadhaar_number", models.CharField(blank=True, default="", max_length=20)),
                ("aadhaar_front", models.ImageField(blank=True, null=True, upload_to=volunteers.models.verification_doc_path)),
                ("aadhaar_back", models.ImageField(blank=True, null=True, upload_to=volunteers.models.verification_doc_path)),
                ("pan_number", models.CharField(blank=True, default="", max_length=20)),
                ("pan_front", models.ImageField(blank=True, null=True, upload_to=volunteers.models.verification_doc_path)),
                ("pan_back", models.ImageField(blank=True, null=True, upload_to=volunteers.models.verification_doc_path)),
                ("license_number", models.CharField(blank=True, default="", max_length=30)),
                ("license_front", models.ImageField(blank=True, null=True, upload_to=volunteers.models.verification_doc_path)),
                ("license_back", models.ImageField(blank=True, null=True, upload_to=volunteers.models.verification_doc_path)),
                ("live_photo", models.ImageField(blank=True, null=True, upload_to=volunteers.models.verification_doc_path)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "volunteer",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="verification", to="volunteers.volunteer",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="VolunteerApproval",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference_comment", models.TextField(blank=True, default="")),
                (
                    "reference_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"), ("approved", "Approved"),
                            ("rejected", "Rejected"), ("auto_rejected", "Auto Rejected"),
                        ],
                        default="pending", max_length=20,
                    ),
                ),
                ("reference_action_at", models.DateTimeField(blank=True, null=True)),
                (
                    "admin_status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                        default="pending", max_length=20,
                    ),
                ),
                ("admin_action_at", models.DateTimeField(blank=True, null=True)),
                ("auto_rejected", models.BooleanField(default=False)),
                ("deadline", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "admin_action_by",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                        related_name="volunteer_admin_actions", to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reference_volunteer",
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reference_approvals", to="volunteers.volunteer",
                    ),
                ),
                (
                    "volunteer",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval", to="volunteers.volunteer",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=100)),
                ("detail", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "volunteer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="audit_logs", to="volunteers.volunteer",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=150)),
                ("message", models.CharField(max_length=500)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("volunteer_approval_required", "Volunteer Approval Required"),
                            ("new_volunteer_application", "New Volunteer Application"),
                            ("status_update", "Status Update"),
                        ],
                        max_length=40,
                    ),
                ),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="volunteer_notifications", to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "related_volunteer",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                        to="volunteers.volunteer",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
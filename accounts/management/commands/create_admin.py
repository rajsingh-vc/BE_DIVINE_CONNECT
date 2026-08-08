import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Create or update the console admin superuser from env vars. Safe to run on every deploy."

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD", "Admin@12345")
        email = os.environ.get("ADMIN_EMAIL", "admin@sansthan.local")

        with transaction.atomic():
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email},
            )
            user.email = email
            user.is_staff = True
            user.is_superuser = True
            if hasattr(user, "user_type"):
                user.user_type = "admin"
            if hasattr(user, "is_active"):
                user.is_active = True
            user.set_password(password)
            user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} admin user '{username}'."))
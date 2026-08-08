from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    """
    Promote an existing user to admin — sets is_staff=True and user_type="admin".

    Use this for accounts that were created through the normal signup flow
    (devotee/volunteer signup) but should actually have admin rights, instead
    of hand-editing them in a Django shell every time.

    Usage:
        python manage.py promote_admin --username someuser
        python manage.py promote_admin --email someone@example.com
        python manage.py promote_admin --username someuser --superuser
    """

    help = "Promote an existing user to admin (is_staff=True, user_type='admin')."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username", type=str, default=None,
            help="Username of the account to promote.",
        )
        parser.add_argument(
            "--email", type=str, default=None,
            help="Email of the account to promote (alternative to --username).",
        )
        parser.add_argument(
            "--superuser", action="store_true",
            help="Also grant is_superuser (full Django admin site access).",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options.get("username")
        email = options.get("email")

        if not username and not email:
            raise CommandError("Provide --username or --email to identify the account.")

        try:
            if username:
                user = User.objects.get(username=username)
            else:
                user = User.objects.get(email=email)
        except User.DoesNotExist:
            identifier = username or email
            raise CommandError(f"No user found matching '{identifier}'.")

        with transaction.atomic():
            user.is_staff = True
            if hasattr(user, "user_type"):
                user.user_type = "admin"
            if options.get("superuser"):
                user.is_superuser = True
            if hasattr(user, "is_active"):
                user.is_active = True
            user.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Promoted '{user.username}' ({user.email}) to admin. "
                f"is_staff={user.is_staff}, user_type={getattr(user, 'user_type', 'n/a')}, "
                f"is_superuser={user.is_superuser}."
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Ask them to log out and log back in so a fresh token/session picks up the change."
            )
        )
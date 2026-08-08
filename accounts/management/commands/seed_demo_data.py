"""
Optional dev-only helper: creates a handful of demo records so the frontend
has something to show right after `migrate`. Not required for the app to
function — every list still comes from the database, nothing is hardcoded
in the frontend or in views. Run with: python manage.py seed_demo_data
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from bookings.models import Booking, Seva
from devotees.models import Devotee
from donations.models import Donation
from events.models import Event, Visitor
from inventory.models import InventoryItem
from volunteers.models import Volunteer

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the database with demo data for local development."

    def handle(self, *args, **options):
        if not User.objects.filter(username="admin").exists():
            admin = User.objects.create_superuser(
                username="admin", email="admin@sansthan.org", password="Admin@12345",
                full_name="Console Admin", user_type=User.UserType.ADMIN,
            )
            self.stdout.write(self.style.SUCCESS(f"Created admin user: admin / Admin@12345"))
        else:
            admin = User.objects.get(username="admin")

        seva, _ = Seva.objects.get_or_create(
            name="Maha Moodganapati Seva",
            defaults=dict(category="Grand Pooja", price=5100, duration_minutes=45, slots_per_day=4,
                          capacity=50, priest="Pt. Ramesh Shastri", description="Grand pooja at the sanctum."),
        )

        if not User.objects.filter(username="devotee1").exists():
            u = User.objects.create_user(username="devotee1", email="devotee1@test.com", password="Devotee@123",
                                          full_name="Ramesh Iyer", user_type=User.UserType.DEVOTEE)
            devotee = Devotee.objects.create(
                user=u, full_name=u.full_name, email=u.email, mobile="+91 9800000000", city="Mumbai"
            )
            Booking.objects.create(devotee=devotee, seva=seva, date="2026-08-01", slot="6:00 AM", amount=5100)
            Donation.objects.create(devotee=devotee, amount=1000, purpose=Donation.Purpose.GENERAL)

        if not User.objects.filter(username="volunteer1").exists():
            u = User.objects.create_user(username="volunteer1", email="volunteer1@test.com", password="Volunteer@123",
                                          full_name="Arjun Mehta", user_type=User.UserType.VOLUNTEER)
            Volunteer.objects.create(
                user=u, full_name=u.full_name, email=u.email, status=Volunteer.Status.ACTIVE, zone="Gate 1",
                volunteer_type=Volunteer.VolunteerType.PERMANENT,
                assigned_seva="Gate Duty", shift="Morning", hours_logged=42,
                home_address="221 MG Road, Mumbai", id_proof_type=Volunteer.IdProofType.AADHAAR,
                id_proof_number="XXXX-XXXX-4821",
            )

        Event.objects.get_or_create(name="Rath Yatra", defaults=dict(date="2026-08-08", status=Event.Status.UPCOMING))
        Visitor.objects.get_or_create(name="Priya Sharma", defaults=dict(zone="Sanctum", party_size=4))
        InventoryItem.objects.get_or_create(sku="PRS-001", defaults=dict(item_name="Laddoo Prasad (box)", stock=1240, min_threshold=500))

        self.stdout.write(self.style.SUCCESS("Demo data seeded."))

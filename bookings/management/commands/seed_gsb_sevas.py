"""
Seeds the Seva catalogue with the real seva & tulabhar list used by
GSB Seva Mandal's Online Seva Booking page
(web.gsbsevamandal.org/sevas/booking), replacing the old placeholder
"Grand Pooja / Daily / Special / Charity" scrap data.

Run with:
    python manage.py seed_gsb_sevas

Safe to re-run — it upserts by name (get_or_create + update), so pricing
can be refreshed each year by editing SEVAS below and re-running, rather
than hardcoding values anywhere in the frontend.

category is one of:
    "Seva"      — main festival sevas/poojas
    "Daily"     — smaller everyday poojas, offered every day of the
                  festival (drives the "Daily Seva" tab)
    "Tulabhar"  — weighing-ritual offerings

is_popular flags the curated set shown first on the "Popular Seva" tab.
"""

from django.core.management.base import BaseCommand

from bookings.models import Seva

# (name, category, price, is_popular)
SEVAS = [
    ("Ekottara Sahasra Maha Ganayaga", "Seva", 705705.00, True),
    ("Maha Santarpan Seva", "Seva", 393325.00, True),
    ("Udayastaman Mahabhog Seva", "Seva", 250875.00, False),
    ("Vigraha Yogadaan Seva", "Seva", 200055.00, False),
    ("Phalahara Seva", "Seva", 199675.00, False),
    ("Ati Vishesh Seva", "Seva", 160355.00, False),
    ("Udayastamana Seva", "Seva", 104955.00, True),
    ("Ashtottara Shata Ganahoma Seva", "Seva", 76155.00, False),
    ("Maha Moodganapati Pooja", "Seva", 75755.00, True),
    ("Anna Daan Seva", "Seva", 36305.00, True),
    ("Sahasra Modak Havana", "Seva", 27505.00, False),
    ("Sahasra Bhojan Seva", "Seva", 17575.00, False),
    ("Full Day Seva", "Seva", 16305.00, False),
    ("Brahman & Suvasini Santarpana", "Seva", 7605.00, False),
    ("Moodganapati Pooja", "Daily", 7575.00, True),
    ("Madhyahna Pooja", "Daily", 6775.00, False),
    ("Bhagirathi Abhishek", "Seva", 6205.00, False),
    ("Ratra Pooja", "Daily", 5655.00, False),
    ("Kshirabhishek", "Seva", 4905.00, False),
    ("Full Day Flower Seva", "Daily", 3655.00, False),
    ("Panaka Seva", "Daily", 3375.00, False),
    ("Ranga Pooja", "Daily", 3075.00, False),
    ("1001 Modak Naivedya", "Seva", 3055.00, False),
    ("Usha Pooja", "Daily", 1825.00, False),
    ("Deeparadhana Seva", "Daily", 1725.00, False),
    ("Haldi Kumukum Seva", "Seva", 1125.00, False),
    ("Flower Pooja", "Daily", 1055.00, False),
    ("Vhar Bhet (Married Couple Only)", "Seva", 805.00, False),
    ("Ganahoma", "Daily", 705.00, False),
    ("Modak Naivedya", "Daily", 625.00, True),
    ("Durva Archana Seva", "Daily", 575.00, False),
    ("Prasad Vitarana Seva", "Daily", 555.00, False),
    # Tulabhar
    ("Coconut Tulabhar (Upto 12 yrs)", "Tulabhar", 1105.00, False),
    ("Coconut Tulabhar (Above 12 yrs)", "Tulabhar", 2105.00, False),
    ("Coconut Tulabhar (Joint - Mother & Child)", "Tulabhar", 3205.00, False),
    ("Panchakajaya Tulabhar (Upto 12 yrs)", "Tulabhar", 1355.00, False),
    ("Panchakajaya Tulabhar (Above 12 yrs)", "Tulabhar", 2205.00, False),
    ("Panchakajaya Tulabhar (Joint - Mother & Child)", "Tulabhar", 3555.00, False),
    ("Sugar Tulabhar (Upto 12 yrs)", "Tulabhar", 2375.00, False),
    ("Sugar Tulabhar (Above 12 yrs)", "Tulabhar", 4275.00, False),
    ("Sugar Tulabhar (Joint - Mother & Child)", "Tulabhar", 5605.00, False),
    ("Rice Tulabhar (Upto 12 yrs)", "Tulabhar", 2625.00, False),
    ("Rice Tulabhar (Above 12 yrs)", "Tulabhar", 4575.00, False),
    ("Rice Tulabhar (Joint - Mother & Child)", "Tulabhar", 5775.00, False),
    ("Banana/Jag/Lahi Tulabhar (Upto 12 yrs)", "Tulabhar", 3825.00, False),
    ("Banana/Jag/Lahi Tulabhar (Above 12 yrs)", "Tulabhar", 5725.00, False),
    ("Banana/Jag/Lahi Tulabhar (Joint - Mother & Child)", "Tulabhar", 7455.00, False),
    ("Laadu Tulabhar (Upto 12 yrs)", "Tulabhar", 9155.00, False),
    ("Laadu Tulabhar (Above 12 yrs)", "Tulabhar", 11955.00, False),
    ("Laadu Tulabhar (Joint - Mother & Child)", "Tulabhar", 13655.00, False),
    ("Modak Tulabhar (Upto 12 yrs)", "Tulabhar", 10955.00, False),
    ("Modak Tulabhar (Above 12 yrs)", "Tulabhar", 13705.00, False),
    ("Modak Tulabhar (Joint - Mother & Child)", "Tulabhar", 17275.00, False),
    ("Dudhpak Tulabhar (Upto 12 yrs)", "Tulabhar", 8675.00, False),
    ("Dudhpak Tulabhar (Above 12 yrs)", "Tulabhar", 11575.00, False),
    ("Dudhpak Tulabhar (Joint - Mother & Child)", "Tulabhar", 14255.00, False),
]


class Command(BaseCommand):
    help = "Seed/refresh the Seva catalogue with the real GSB Seva Mandal seva & tulabhar list."

    def handle(self, *args, **options):
        created, updated = 0, 0
        for name, category, price, is_popular in SEVAS:
            obj, was_created = Seva.objects.update_or_create(
                name=name,
                defaults={
                    "category": category,
                    "price": price,
                    "is_popular": is_popular,
                    "is_active": True,
                },
            )
            created += was_created
            updated += not was_created

        self.stdout.write(self.style.SUCCESS(f"Seva catalogue seeded: {created} created, {updated} updated."))

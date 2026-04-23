# accounts/management/commands/seed_packages.py
from django.core.management.base import BaseCommand
from accounts.models import PackageCatalog

DEFAULTS = [
    ("launch-starter","Launch Starter",  79900, "one-time"),
    ("business-essentials","Business Essentials",149900,"one-time"),
    ("growth-plus","Growth Plus",        239900,"one-time"),
    ("care-basic","Care Basic (Monthly)", 3900, "subscription"),
    ("care-plus","Care Plus (Monthly)",   7900, "subscription"),
    ("care-pro","Care Pro (Monthly)",    14900, "subscription"),
]

class Command(BaseCommand):
    help = "Seed or update default package catalog entries"

    def handle(self, *args, **opts):
        created, updated = 0, 0
        for slug, name, price, type_ in DEFAULTS:
            obj, was_created = PackageCatalog.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "price_cents": price, "type": type_},
            )
            created += 1 if was_created else 0
            updated += 0 if was_created else 1
        self.stdout.write(self.style.SUCCESS(
            f"Seed complete. Created {created}, updated {updated}."
        ))

# accounts/management/commands/cleanup_unverified.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from accounts.models import CustomerAccount, EmailVerificationToken

User = get_user_model()

class BaseCommand(BaseCommand):
    help = "Delete users who signed up but never verified within 24 hours."

    def handle(self, *args, **kwargs):
        cutoff = timezone.now() - timedelta(hours=24)
        tokens = (EmailVerificationToken.objects
                  .filter(created_at__lt=cutoff)
                  .select_related("user"))
        deleted_users = 0
        for t in tokens:
            try:
                ca = CustomerAccount.objects.get(customer=t.user)
                if not ca.email_verified_at:
                    t.user.delete()
                    deleted_users += 1
            except CustomerAccount.DoesNotExist:
                t.user.delete()
                deleted_users += 1
            t.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_users} unverified user(s)."))

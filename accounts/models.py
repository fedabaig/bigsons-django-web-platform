# accounts/models.py
"""
Commerce + Ops models for BigSons
- PackageCatalog: price list you sell from
- UserPackage: a customer's purchased plan / project state
- Payment: money received (stored in cents; display in dollars)
- CustomerAccount: links a customer to their Account Manager (staff)
- Task: internal work tasks assigned to staff (optionally tied to a customer/package)
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
# --- Email verification token (24h expiry) ---
import uuid

# Use the configured user model (string "app_label.ModelName")
# This keeps the file compatible if you ever swap the user model.
User = settings.AUTH_USER_MODEL


# =========================
# 1) Price list (catalog)
# =========================
class PackageCatalog(models.Model):
    """
    A sellable plan/package with a price and type.
    Example: "Launch Starter" (one-time) or "Care Basic" (subscription)
    """
    TYPE_CHOICES = (
        ("one-time", "One-time"),
        ("subscription", "Subscription"),
    )

    slug = models.SlugField(unique=True)                 # URL-safe identifier (e.g., "launch-starter")
    name = models.CharField(max_length=120)              # Human label
    price_cents = models.PositiveIntegerField(default=0) # Stored in *cents* to avoid float mistakes
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="one-time")
    icon = models.CharField(max_length=255, blank=True)  # Optional static path/class for UI

    def __str__(self) -> str:
        return self.name

    @property
    def price_display(self) -> str:
        """Dollar-formatted price, e.g. $1,499.00 (derived from price_cents)."""
        return "${:,.2f}".format(self.price_cents / 100)

    @property
    def is_subscription(self) -> bool:
        """Convenience flag used in templates/UI."""
        return self.type == "subscription"


# ==========================================
# 2) What a specific user purchased/owns
# ==========================================
class UserPackage(models.Model):
    """
    A customer's active/paused/canceled package, with build progress steps.
    Billing/percent logic lives here (30/40/30 tranche design).
    """
    
    STATUS_CHOICES = [
        ("in_progress", "In progress"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("canceled", "Canceled"),
    ]

    # --- add this helper inside UserPackage ---
    def is_subscription(self) -> bool:
     return getattr(self.package, "type", "") == "subscription"

    # Step markers for the 30/40/30 plan:
    STEP_CHOICES = [(0, "deposit"), (1, "design"), (2, "final"), (3, "complete")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)          # The customer
    package = models.ForeignKey(PackageCatalog, on_delete=models.CASCADE)                 # What they bought
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_progress")
    step = models.IntegerField(choices=STEP_CHOICES, default=0)                           # Current tranche/phase
    paid_cents = models.PositiveIntegerField(default=0)                                   # Total paid so far (cents)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]                          # newest first in admin
        indexes = [
            models.Index(fields=["user"]),                  # common lookup
            models.Index(fields=["status"]),                # filter in dashboards
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.package.name}"

    # -------- Computed money/progress helpers (kept in cents internally) --------
    @property
    def price_cents(self) -> int:
        """Mirror of the package's list price (kept centralized in catalog)."""
        return self.package.price_cents

    @property
    def due_cents(self) -> int:
        """Remaining amount (cents)."""
        return max(0, self.price_cents - self.paid_cents)

    @property
    def paid_percent(self) -> int:
        """Integer 0..100 showing progress paid vs price."""
        total = self.price_cents or 0
        if total <= 0:
            return 0
        pct = round(self.paid_cents * 100 / total)
        return max(0, min(100, pct))

    @property
    def paid_display(self) -> str:
        """Dollar string of paid so far (e.g., $299.70)."""
        return "${:,.2f}".format(self.paid_cents / 100)

    @property
    def due_display(self) -> str:
        """Dollar string of due amount (e.g., $1,199.30)."""
        return "${:,.2f}".format(self.due_cents / 100)

  

    @property
    def next_partial_cents(self) -> int:
        """
        For subscriptions: always charge the full monthly price.
        For one-time builds: keep 30/40/30.
        """
        if self.is_subscription():
            return int(self.price_cents or 0)

        # --- existing milestone logic (unchanged) ---
        if self.step >= 3:      # already complete
            return 0
        total = self.price_cents
        parts = [0.30, 0.40, 0.30]
        raw = int(round(total * parts[self.step]))
        return min(raw, self.due_cents)


    @property
    def next_milestone_label(self) -> str:
        """Human label for the next step (used by the dashboard UI)."""
        labels = {
            0: "Deposit (30%)",
            1: "Design approval (40%)",
            2: "Final payment (30%)",
            3: "Complete",
        }
        return labels.get(self.step, "Next")

    @property
    def next_milestone_date(self):
        """
        Placeholder if you want to schedule forecasting later.
        Return None for now (template prints a dash).
        """
        return None

    def apply_payment(self, amount_cents: int) -> None:
        """
        Add a payment to this package, advance tranche/step accordingly,
        and update status to 'active' when fully paid.
        """
        amount_cents = max(0, int(amount_cents or 0))
        if amount_cents == 0:
            return

        # Cap paid to the list price
        self.paid_cents = min(self.price_cents, self.paid_cents + amount_cents)

        # Full paid → final state
        if self.due_cents == 0:
            self.step = 3
            self.status = "active"
            return

        # Partial progress → compute tranche step
        total = self.price_cents or 0
        cumulative = (self.paid_cents / total) if total else 0.0

        if cumulative >= 1.0:
            self.step = 3
            self.status = "active"
        elif cumulative >= 0.70:
            self.step = 2
            self.status = "in_progress"
        elif cumulative >= 0.30:
            self.step = 1
            self.status = "in_progress"
        else:
            self.step = 0
            self.status = "in_progress"


# ==========================
# 3) Payment ledger (cash)
# ==========================
class Payment(models.Model):
    """
    A single payment event from a user for a specific UserPackage.
    Store integer cents; render dollars with amount_display.
    """
    STATUS_CHOICES = [("paid", "Paid"), ("failed", "Failed")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)   # Who paid
    user_package = models.ForeignKey(
        UserPackage, on_delete=models.CASCADE, related_name="payments"             # Payment belongs to one project
    )
    amount_cents = models.PositiveIntegerField()                                   # Integer cents (e.g., 2935)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="paid")
    created_at = models.DateTimeField(default=timezone.now)
    # NEW ↓↓↓
    provider = models.CharField(max_length=32, blank=True, default="")        # e.g. "stripe"
    provider_ref = models.CharField(max_length=255, blank=True, default="") 

    class Meta:
        ordering = ["-created_at"]  # newest first
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
            models.Index(fields=["provider", "provider_ref"]),  # NEW
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.user_package.package.name} · {self.amount_display}"

    @property
    def amount_display(self) -> str:
        """Dollar string (e.g., 2935 -> '$29.35')."""
        return "${:,.2f}".format(self.amount_cents / 100)


# =====================================
# 4) Customer account / owner metadata
# =====================================
class CustomerAccount(models.Model):
    """
    Admin-only view of a customer's meta + their assigned Account Manager (who is staff).
    Useful for reporting, ownership, and routing.
    """
    customer = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="customer_account"
    )
    account_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="managed_customers",
        limit_choices_to={"is_staff": True},
    )
    tier = models.CharField(max_length=30, default="standard")
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    # extras
    phone = models.CharField(max_length=30, blank=True)              # optional
    email_verified_at = models.DateTimeField(null=True, blank=True)  # set when verified

    def __str__(self):
        return f"CustomerAccount({self.customer})"

    @property
    def is_email_verified(self) -> bool:
        return bool(self.email_verified_at)

# ==========================
# 5) Internal staff tasks
# ==========================
class Task(models.Model):
    """
    Internal work items assigned to *staff*.
    Optionally tie a task to a customer (context) and/or a specific UserPackage.
    """
    PRIORITY_CHOICES = (("low", "Low"), ("normal", "Normal"), ("high", "High"))
    STATUS_CHOICES = (("todo", "To do"), ("doing", "In progress"), ("done", "Done"))

    # Who does the work → must be staff:
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assigned_tasks",
        limit_choices_to={"is_staff": True},  # enforce staff
    )

    # Context: which customer is this for (optional; must be non-staff):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="customer_context_tasks",
        limit_choices_to={"is_staff": False},  # enforce non-staff (customers)
    )

    # Optionally tie to a concrete purchased plan:
    user_package = models.ForeignKey(
        "accounts.UserPackage",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="tasks",
    )

    title = models.CharField(max_length=200)                        # Short task title
    description = models.TextField(blank=True)                      # Details / acceptance criteria
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="normal")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="todo")

    start_date = models.DateField(null=True, blank=True)            # When we plan to start
    due_date = models.DateField(null=True, blank=True)              # Deadline (optional)
    completed_at = models.DateTimeField(null=True, blank=True)      # Timestamp when set to done

    created_by = models.ForeignKey(                                 # Who created the task (often admin/manager)
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="created_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        who = getattr(self.assignee, "username", "?")
        return f"[{self.priority}] {self.title} → {who}"

class EmailVerificationToken(models.Model):
    """
    One-time email verification token for a user. Expires in 24 hours.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verify_tokens",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self) -> bool:
        return timezone.now() > self.created_at + timezone.timedelta(hours=24)

    def __str__(self):
        return f"EmailVerificationToken<{self.user_id}:{self.token}>"
    

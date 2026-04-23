# accounts/admin.py
"""
Admin for:
- PackageCatalog (price list)
- UserPackage (what a user owns / build state)
- Payment (ledger)
- CustomerAccount (read-only activity overview for superusers)
- Task (work assigned to STAFF; customer is optional context)

Key features:
- Currency edits in ADMIN use *dollars* (29.35) and are stored as cents under the hood.
- Task workload helpers: overdue filter, quick actions, colored badges.
- Bulk-create tasks for selected STAFF from the User admin.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Count, Sum
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.utils.timezone import localdate

from .models import (
    PackageCatalog, UserPackage, Payment,
    CustomerAccount, Task,
)

User = get_user_model()

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def cents_to_dollars(cents: int) -> str:
    """Render cents -> '$1,234.56'."""
    cents = cents or 0
    return "${:,.2f}".format(cents / 100)

def _to_cents_from_dollars(val) -> int:
    """
    Convert a decimal/string dollar value to integer cents.
    Raises ValueError if invalid.
    """
    if val in (None, ""):
        return 0
    try:
        d = Decimal(str(val))
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid dollar amount.")
    return int(round(d * 100))


# ------------------------------------------------------------
# Task list filter + quick actions (MUST be defined before TaskAdmin)
# ------------------------------------------------------------

class OverdueListFilter(admin.SimpleListFilter):
    """Sidebar filter for Task changelist: Overdue / Today / Upcoming / No due date."""
    title = "Due status"
    parameter_name = "due_status"

    def lookups(self, request, model_admin):
        return (
            ("overdue", "Overdue"),
            ("today", "Due today"),
            ("upcoming", "Upcoming"),
            ("none", "No due date"),
        )

    def queryset(self, request, qs):
        today = date.today()
        val = self.value()
        if val == "overdue":
            return qs.filter(due_date__lt=today, status__in=["todo", "doing"])
        if val == "today":
            return qs.filter(due_date=today, status__in=["todo", "doing"])
        if val == "upcoming":
            return qs.filter(due_date__gt=today, status__in=["todo", "doing"])
        if val == "none":
            return qs.filter(due_date__isnull=True)
        return qs


@admin.action(description="Mark selected as DONE")
def mark_done(modeladmin, request, queryset):
    updated = queryset.update(status="done")
    messages.success(request, f"Marked {updated} task(s) as done.")

@admin.action(description="Mark selected as DOING")
def mark_doing(modeladmin, request, queryset):
    updated = queryset.update(status="doing")
    messages.success(request, f"Moved {updated} task(s) to In progress.")

@admin.action(description="Set priority → HIGH")
def set_priority_high(modeladmin, request, queryset):
    updated = queryset.update(priority="high")
    messages.info(request, f"Set HIGH priority on {updated} task(s).")


# ------------------------------------------------------------
# Currency-in-dollars ModelForms (ADMIN only)
# ------------------------------------------------------------

class PackageCatalogAdminForm(forms.ModelForm):
    # Replace price_cents with user-facing price_dollars
    price_dollars = forms.DecimalField(
        label="Price ($)", min_value=Decimal("0.00"), decimal_places=2, max_digits=12
    )

    class Meta:
        model = PackageCatalog
        fields = ("name", "slug", "type", "icon")  # no price_cents here; we expose price_dollars instead

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cents = getattr(self.instance, "price_cents", 0) or 0
        self.fields["price_dollars"].initial = Decimal(cents) / Decimal(100)

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.price_cents = _to_cents_from_dollars(self.cleaned_data.get("price_dollars"))
        if commit:
            obj.save()
        return obj


class PaymentAdminForm(forms.ModelForm):
    amount_dollars = forms.DecimalField(
        label="Amount ($)", min_value=Decimal("0.00"), decimal_places=2, max_digits=12
    )

    class Meta:
        model = Payment
        fields = ("user", "user_package", "status")  # amount_cents replaced

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cents = getattr(self.instance, "amount_cents", 0) or 0
        self.fields["amount_dollars"].initial = Decimal(cents) / Decimal(100)

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.amount_cents = _to_cents_from_dollars(self.cleaned_data.get("amount_dollars"))
        if commit:
            obj.save()
        return obj


class UserPackageAdminForm(forms.ModelForm):
    # Optional: allow editing paid_dollars directly (admin convenience)
    paid_dollars = forms.DecimalField(
        label="Paid ($)", min_value=Decimal("0.00"), decimal_places=2, max_digits=12, required=False
    )

    class Meta:
        model = UserPackage
        fields = ("user", "package", "status", "step")  # paid_cents replaced

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cents = getattr(self.instance, "paid_cents", 0) or 0
        self.fields["paid_dollars"].initial = Decimal(cents) / Decimal(100)

    def save(self, commit=True):
        obj = super().save(commit=False)
        # If provided, update paid_cents from paid_dollars
        if "paid_dollars" in self.cleaned_data and self.cleaned_data["paid_dollars"] is not None:
            obj.paid_cents = _to_cents_from_dollars(self.cleaned_data["paid_dollars"])
        if commit:
            obj.save()
        return obj


# Inlines also edit in dollars
class PaymentInlineForm(forms.ModelForm):
    amount_dollars = forms.DecimalField(
        label="Amount ($)", min_value=Decimal("0.00"), decimal_places=2, max_digits=12
    )

    class Meta:
        model = Payment
        fields = ("user_package", "status")  # amount_cents replaced

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cents = getattr(self.instance, "amount_cents", 0) or 0
        self.fields["amount_dollars"].initial = Decimal(cents) / Decimal(100)

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.amount_cents = _to_cents_from_dollars(self.cleaned_data.get("amount_dollars"))
        if commit:
            obj.save()
        return obj


class UserPackageInlineForm(forms.ModelForm):
    paid_dollars = forms.DecimalField(
        label="Paid ($)", min_value=Decimal("0.00"), decimal_places=2, max_digits=12, required=False
    )

    class Meta:
        model = UserPackage
        fields = ("package", "status", "step")  # paid_cents replaced

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cents = getattr(self.instance, "paid_cents", 0) or 0
        self.fields["paid_dollars"].initial = Decimal(cents) / Decimal(100)

    def save(self, commit=True):
        obj = super().save(commit=False)
        if "paid_dollars" in self.cleaned_data and self.cleaned_data["paid_dollars"] is not None:
            obj.paid_cents = _to_cents_from_dollars(self.cleaned_data["paid_dollars"])
        if commit:
            obj.save()
        return obj


# ------------------------------------------------------------
# Inlines on User admin (now show/edit dollars)
# ------------------------------------------------------------

class UserPackageInline(admin.TabularInline):
    model = UserPackage
    form = UserPackageInlineForm
    extra = 0
    fields = ("package", "status", "step", "paid_dollars", "created_at")  # dollars field
    readonly_fields = ("created_at",)
    autocomplete_fields = ("package",)
    ordering = ("-created_at",)
    show_change_link = True


class PaymentInline(admin.TabularInline):
    model = Payment
    form = PaymentInlineForm
    extra = 0
    fields = ("user_package", "amount_dollars", "status", "created_at")  # dollars field
    readonly_fields = ("created_at",)
    autocomplete_fields = ("user_package",)
    ordering = ("-created_at",)
    show_change_link = True


# ------------------------------------------------------------
# PackageCatalog (price list) — edit price in dollars
# ------------------------------------------------------------

@admin.register(PackageCatalog)
class PackageCatalogAdmin(admin.ModelAdmin):
    form = PackageCatalogAdminForm
    list_display = ("name", "slug", "type", "price_dollars")
    list_filter = ("type",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("type", "name")

    @admin.display(description="Price ($)", ordering="price_cents")
    def price_dollars(self, obj):
        return cents_to_dollars(obj.price_cents)


# ------------------------------------------------------------
# UserPackage — list shows dollars, form edits paid_dollars
# ------------------------------------------------------------

@admin.action(description="Mark selected as Canceled")
def mark_canceled(modeladmin, request, queryset):
    queryset.update(status="canceled")

@admin.action(description="Mark selected as Active")
def mark_active(modeladmin, request, queryset):
    queryset.update(status="active")

@admin.register(UserPackage)
class UserPackageAdmin(admin.ModelAdmin):
    form = UserPackageAdminForm
    list_display = (
        "id", "user", "package", "status", "step",
        "price_dollars", "paid_dollars_col", "due_dollars", "created_at",
    )
    list_filter = ("status", "package__type", "step", "created_at")
    search_fields = ("user__username", "user__email", "package__name", "package__slug")
    autocomplete_fields = ("user", "package")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    actions = [mark_canceled, mark_active]

    @admin.display(description="Price ($)")
    def price_dollars(self, obj):
        return cents_to_dollars(getattr(obj.package, "price_cents", 0))

    @admin.display(description="Paid ($)")
    def paid_dollars_col(self, obj):
        return cents_to_dollars(obj.paid_cents)

    @admin.display(description="Due ($)")
    def due_dollars(self, obj):
        return cents_to_dollars(obj.due_cents)


# ------------------------------------------------------------
# Payment — edit amount in dollars
# ------------------------------------------------------------

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    form = PaymentAdminForm
    list_display = ("id", "user", "package_name", "amount_dollars", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = (
        "user__username", "user__email",
        "user_package__package__name", "user_package__package__slug",
    )
    autocomplete_fields = ("user", "user_package")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    @admin.display(description="Amount ($)", ordering="amount_cents")
    def amount_dollars(self, obj):
        return cents_to_dollars(obj.amount_cents)

    @admin.display(description="Package")
    def package_name(self, obj):
        return obj.user_package.package.name if obj.user_package and obj.user_package.package else "—"


# ------------------------------------------------------------
# Customer activity (READ-ONLY, superuser only)
# ------------------------------------------------------------

# Make registration idempotent (avoids AlreadyRegistered during autoreload)
try:
    admin.site.unregister(CustomerAccount)
except admin.sites.NotRegistered:
    pass

@admin.register(CustomerAccount)
class CustomerAccountAdmin(admin.ModelAdmin):
    """
    Read-only customer activity for superusers.
    """
    def has_module_permission(self, request): return request.user.is_superuser
    def has_view_permission(self, request, obj=None): return request.user.is_superuser
    def has_add_permission(self, request): return request.user.is_superuser
    def has_change_permission(self, request, obj=None): return request.user.is_superuser
    def has_delete_permission(self, request, obj=None): return request.user.is_superuser

    list_display = (
        "customer_username", "email", "manager_username",
        "tier", "package_count", "payment_count", "total_paid_display", "created_at",
    )
    list_select_related = ("customer", "account_manager")
    search_fields = ("customer__username", "customer__email", "account_manager__username")
    list_filter = ("tier", "account_manager")
    autocomplete_fields = ("customer", "account_manager")
    ordering = ("tier", "customer__username")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _pkg_count=Count("customer__userpackage", distinct=True),
            _pay_count=Count("customer__payment", distinct=True),
            _paid_sum=Sum("customer__payment__amount_cents"),
        )

    @admin.display(description="Customer")
    def customer_username(self, obj): 
        return getattr(obj.customer, "username", "—")

    @admin.display(description="Email")
    def email(self, obj): 
        return getattr(obj.customer, "email", "—")

    @admin.display(description="Account Manager")
    def manager_username(self, obj): 
        return getattr(obj.account_manager, "username", "Unassigned")

    @admin.display(description="# Packages")
    def package_count(self, obj): 
        return getattr(obj, "_pkg_count", 0)

    @admin.display(description="# Payments")
    def payment_count(self, obj): 
        return getattr(obj, "_pay_count", 0)

    @admin.display(description="Total Paid")
    def total_paid_display(self, obj): 
        return "${:,.2f}".format((getattr(obj, "_paid_sum", 0) or 0) / 100)


# ------------------------------------------------------------
# Task admin (STAFF assignees only) — uses filter/actions above
# ------------------------------------------------------------

class TaskAdminForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = "__all__"

    def clean_assignee(self):
        user = self.cleaned_data["assignee"]
        if not user.is_staff:
            raise forms.ValidationError("Assignee must be a staff user.")
        return user

    def clean_customer(self):
        cust = self.cleaned_data.get("customer")
        if cust and cust.is_staff:
            raise forms.ValidationError("Customer must be a non-staff user.")
        return cust


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """
    Tasks are designated to staff (assignee). Customer is optional context.
    Admin shows workload-friendly signals (overdue/today/upcoming) and actions.
    """
    form = TaskAdminForm

    list_display = (
        "title", "assignee", "customer",
        "priority_badge", "status_badge",
        "due_date", "due_hint",
        "created_at",
    )
    list_filter = ("priority", "status", OverdueListFilter, "assignee", "due_date")
    search_fields = ("title", "description", "assignee__username", "customer__username")
    autocomplete_fields = ("assignee", "customer", "user_package", "created_by")
    date_hierarchy = "created_at"
    ordering = ("status", "priority", "due_date", "-created_at")
    list_per_page = 50

    actions = [mark_done, mark_doing, set_priority_high]

    @admin.display(description="Priority", ordering="priority")
    def priority_badge(self, obj):
        color = {"low": "#6b7280", "normal": "#0ea5e9", "high": "#dc2626"}.get(obj.priority, "#6b7280")
        return format_html('<span style="color:{};font-weight:600;">{}</span>', color, obj.priority.title())

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        color = {"todo": "#ef4444", "doing": "#f59e0b", "done": "#16a34a"}.get(obj.status, "#6b7280")
        return format_html('<span style="color:{};font-weight:600;">{}</span>', color, obj.status.title())

    @admin.display(description="Due")
    def due_hint(self, obj):
        if not obj.due_date:
            return format_html('<span style="color:#6b7280;">—</span>')
        today = date.today()
        if obj.due_date < today and obj.status in ("todo", "doing"):
            return format_html('<span style="color:#dc2626;">Overdue</span>')
        if obj.due_date == today and obj.status in ("todo", "doing"):
            return format_html('<span style="color:#b45309;">Today</span>')
        return format_html('<span style="color:#10b981;">Upcoming</span>')


# ------------------------------------------------------------
# Bulk create tasks FOR STAFF (from Users changelist)
# ------------------------------------------------------------

class BulkCreateTasksForStaffForm(forms.Form):
    title = forms.CharField(max_length=200, required=True, help_text="What needs to be done?")
    description = forms.CharField(widget=forms.Textarea, required=False)
    priority = forms.ChoiceField(choices=Task.PRIORITY_CHOICES, initial="normal")
    due_date = forms.DateField(required=False, help_text="Optional (YYYY-MM-DD)")
    customer = forms.ModelChoiceField(
        queryset=User.objects.filter(is_staff=False).order_by("username"),
        required=False,
        help_text="(Optional) Attach tasks to a customer context.",
    )

def bulk_create_tasks_for_staff(modeladmin, request, queryset):
    """
    Admin action on User changelist:
    Select STAFF users and create one task per selected staff.
    """
    staff_qs = queryset.filter(is_staff=True)
    if request.method == "POST" and "apply" in request.POST:
        form = BulkCreateTasksForStaffForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data["title"]
            description = form.cleaned_data.get("description") or ""
            priority = form.cleaned_data["priority"]
            due_date = form.cleaned_data.get("due_date")
            customer = form.cleaned_data.get("customer")

            created = 0
            for staff_user in staff_qs:
                Task.objects.create(
                    title=title,
                    description=description,
                    priority=priority,
                    status="todo",
                    assignee=staff_user,       # ← DESIGNATE TO STAFF
                    customer=customer,         # optional link to a customer
                    user_package=(
                        UserPackage.objects.filter(user=customer).order_by("-created_at").first()
                        if customer else None
                    ),
                    start_date=localdate(),
                    due_date=due_date,
                    created_by=request.user,
                )
                created += 1
            modeladmin.message_user(request, f"Created {created} task(s) for {staff_qs.count()} staff.")
            return None
    else:
        form = BulkCreateTasksForStaffForm()

    context = {
        **admin.site.each_context(request),
        "title": "Create Tasks for Staff",
        "queryset": staff_qs,
        "action": "bulk_create_tasks_for_staff",
        "form": form,
    }
    return TemplateResponse(request, "admin/accounts/confirm_action_form.html", context)

bulk_create_tasks_for_staff.short_description = "Create Task(s) for selected staff…"


# ------------------------------------------------------------
# User admin override (with inlines + staff task action)
# ------------------------------------------------------------

try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Users page:
    - For customers: shows packages/payments inlines (in dollars).
    - For staff: bulk-create tasks via the action; individual tasks live in Task admin.
    """
    inlines = [UserPackageInline, PaymentInline]
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    ordering = ("username",)
    list_per_page = 50

    actions = [bulk_create_tasks_for_staff]

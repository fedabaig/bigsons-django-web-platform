# accounts/views.py
# Messaging + auth decorators
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView
import logging
# Query helpers (Q for search; Count/Sum for aggregates)
from django.db.models import Q, Count, Sum

# Time + pagination
from django.utils.timezone import localdate, timezone
from django.core.paginator import Paginator

# HTTP/shortcuts
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

# Your models (include Task!)
from .models import PackageCatalog, UserPackage, Payment, Task

#signup
from django.core.mail import send_mail
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from .forms import SignupForm, SignupIssueForm
from .models import CustomerAccount
# Email verification flow
from .models import EmailVerificationToken

# Stripe
import stripe

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
#security




log = logging.getLogger(__name__)
User = get_user_model()
signer = TimestampSigner()  # 24h expiry will be enforced at unsign time

@staff_member_required
def staff_users_report(request):
    """
    Staff-only aggregate snapshot of users and their commerce activity.
    Returns counts and total paid (in cents) so the template can format dollars.
    """
    users = (
        User.objects
        .annotate(
            package_count=Count("userpackage", distinct=True),
            payment_count=Count("payment", distinct=True),
            total_paid_cents=Sum("payment__amount_cents"),
        )
        .order_by("-package_count", "username")
    )
    return render(request, "accounts/staff_users_report.html", {"users": users})

# ---------------------------
# Public/entry helpers
# ---------------------------

def signup_disabled(request):
    """
    Hard-block any public signup view you might have linked.
    Keep this view wired to your public signup URL so visitors
    can't self-register.
    """
    return HttpResponseForbidden("Signup is disabled.")


@login_required
def route_after_login(request):
    """
    Post-login router:
    - If the user is in the 'staff' group -> staff dashboard
    - Otherwise -> customer dashboard
    You can also change this to check request.user.is_staff if you prefer.
    """
    if request.user.is_staff or request.user.groups.filter(name="staff").exists():
        return redirect("accounts:staff_dashboard")
    return redirect("accounts:dashboard")


# ---------------------------
# Staff area
# ---------------------------

@staff_member_required
def staff_dashboard(request):
    """
    Staff-only dashboard.
    Keeps your original context keys (page_title, who) and adds:
      - filters: status/due/q
      - kpi: overdue/today/open/done
      - page_obj: paginated task list assigned to the logged-in staff
      - recent_packages / recent_payments: quick customer context for visible tasks
      - today: date for template comparisons
    """
    today = localdate()

    # --- filters from querystring ---
    status = request.GET.get("status", "")         # 'todo' | 'doing' | 'done' | ''
    due = request.GET.get("due", "")               # 'overdue' | 'today' | 'upcoming' | 'none' | ''
    q = (request.GET.get("q") or "").strip()       # search text

    # Base queryset: only tasks assigned to this staff user
    qs = (Task.objects
            .filter(assignee=request.user)
            .select_related("customer", "user_package", "user_package__package")
            .order_by("status", "priority", "due_date", "-created_at"))

    if status in {"todo", "doing", "done"}:
        qs = qs.filter(status=status)

    if due == "overdue":
        qs = qs.filter(due_date__lt=today, status__in=["todo", "doing"])
    elif due == "today":
        qs = qs.filter(due_date=today, status__in=["todo", "doing"])
    elif due == "upcoming":
        qs = qs.filter(due_date__gt=today, status__in=["todo", "doing"])
    elif due == "none":
        qs = qs.filter(due_date__isnull=True)

    if q:
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(customer__username__icontains=q) |
            Q(user_package__package__name__icontains=q)
        )

    # --- KPIs for this staff member ---
    open_qs = Task.objects.filter(assignee=request.user, status__in=["todo", "doing"])
    kpi_overdue = open_qs.filter(due_date__lt=today).count()
    kpi_due_today = open_qs.filter(due_date=today).count()
    kpi_open = open_qs.count()
    kpi_done = Task.objects.filter(assignee=request.user, status="done").count()

    # --- pagination ---
    paginator = Paginator(qs, 12)  # 12 rows per page
    page_obj = paginator.get_page(request.GET.get("page"))

    # --- right-rail context for customers tied to visible tasks ---
    customer_ids = {t.customer_id for t in page_obj if t.customer_id}
    recent_packages = []
    recent_payments = []
    if customer_ids:
        recent_packages = (UserPackage.objects
                           .filter(user_id__in=customer_ids)
                           .select_related("package", "user")
                           .order_by("user_id", "-created_at")[:20])
        recent_payments = (Payment.objects
                           .filter(user_id__in=customer_ids)
                           .select_related("user_package", "user_package__package", "user")
                           .order_by("-created_at")[:20])

    ctx = {
        # your original keys
        "page_title": "Staff Dashboard",
        "who": request.user,

        # new stuff you can use in your existing template
        "filters": {"status": status, "due": due, "q": q},
        "kpi": {"overdue": kpi_overdue, "today": kpi_due_today, "open": kpi_open, "done": kpi_done},
        "page_obj": page_obj,
        "recent_packages": recent_packages,
        "recent_payments": recent_payments,
        "today": today,
    }
    return render(request, "accounts/staff_dashboard.html", ctx)


@staff_member_required
@require_POST
def staff_task_status(request, pk: int):
    """
    Quick status update for a task (todo/doing/done).
    Only the assignee or superusers can change it.
    """
    new_status = request.POST.get("status", "")
    if new_status not in {"todo", "doing", "done"}:
        messages.error(request, "Invalid status.")
        return redirect("accounts:staff_dashboard")

    task = get_object_or_404(Task, pk=pk)
    if not (request.user.is_superuser or task.assignee_id == request.user.id):
        messages.error(request, "You don't have permission to update this task.")
        return redirect("accounts:staff_dashboard")

    task.status = new_status
    if new_status == "done" and not task.completed_at:
        from django.utils import timezone
        task.completed_at = timezone.now()
    task.save()

    messages.success(request, f"Updated “{task.title}” → {new_status.upper()}.")
    return redirect("accounts:staff_dashboard")



# ---------------------------
# Customer dashboard
# ---------------------------

@login_required
def dashboard(request):
    if request.user.is_staff or request.user.groups.filter(name="staff").exists():
        return redirect("accounts:staff_dashboard")
    """
    Customer portal: shows packages, progress, invoices, and actions.
    """
    user_packages = (
        UserPackage.objects
        .filter(user=request.user)
        .select_related("package")
    )
    recent_payments = (
        Payment.objects
        .filter(user=request.user)
        .select_related("user_package")
        .order_by("-created_at")[:10]
    )

    # --- build the packages list for the UI (REPLACE THIS WHOLE BLOCK) ---
    packages_ctx = []
    for up in user_packages:
        is_sub = (getattr(up.package, "type", "") == "subscription")
        price_display = "${:,.2f}".format((up.package.price_cents or 0) / 100)

        # Humanized status
        if up.status == "active":
            status_h = "Active"
        elif up.status == "in_progress":
            status_h = "In progress"
        elif up.status == "paused":
            status_h = "Paused"
        elif up.status == "canceled":
            status_h = "Canceled"
        else:
            status_h = up.status.title() if up.status else "Unknown"

        packages_ctx.append({
            "id": up.id,
            "slug": getattr(up.package, "slug", ""),   # useful for subscribe URLs later
            "name": up.package.name,
            "icon": up.package.icon or "",
            "type": up.package.type,                   # "one-time" | "subscription"
            "price_display": price_display,            # "$39.00 / month" for subs (shown by template text)
            "status": status_h,

            # Progress & amounts (subs hide milestone visuals in the template)
            "paid_percent": (up.paid_percent or 0) if not is_sub else 0,
            "paid_display": "${:,.2f}".format((up.paid_cents or 0) / 100),

            # For one-time builds keep “due”; subs show monthly price instead
            "due_cents": (up.due_cents or 0) if not is_sub else 0,
            "due_display": (
                "${:,.2f}".format((up.due_cents or 0) / 100) if not is_sub else price_display
            ),

            # NEW: exact next tranche for one-time projects
            "next_partial_cents": up.next_partial_cents if not is_sub else 0,
            "next_partial_display": "${:,.2f}".format((up.next_partial_cents or 0) / 100) if not is_sub else "",
            "next_milestone_label": up.next_milestone_label if not is_sub else "",
            "next_milestone_date": up.next_milestone_date if not is_sub else None,

            "is_subscription": is_sub,
            "can_change": True,
            "can_pause": True,
            "can_cancel": True,
            "can_remove": (up.status == "canceled"),
        })



    invoices_ctx = []
    for p in recent_payments:
        invoices_ctx.append({
            "date": p.created_at.strftime("%Y-%m-%d") if p.created_at else "",
            "desc": f"Payment for {p.user_package.package.name}" if p.user_package and p.user_package.package else "Payment",
            "amount": p.amount_display,   # "$39.00"
            "status": "Paid" if p.status == "paid" else "Failed",
            "receipt_url": "",            # wire up later if you add receipts
        })

        

    # Static placeholder (keeps your template happy even without real data)
    account_manager = {
        "name": "Alex Carter",
        "title": "Account Manager",
        "email": "info@bigsonsweb.com",
        "phone": "+1 (463) 2660968",
        "photo": "main/img/manager-placeholder.png",  # ensure file exists at main/static/main/img/...
    }
    email_pending = False
    verify_deadline = None
    try:
        ca = CustomerAccount.objects.select_related("customer").get(customer=request.user)
        email_pending = not bool(ca.email_verified_at)
        if email_pending:
            token = (EmailVerificationToken.objects
                     .filter(user=request.user)
                     .order_by("-created_at")
                     .first())
            verify_deadline = getattr(token, "expires_at", None)
    except CustomerAccount.DoesNotExist:
        email_pending = True  # defensive default


    return render(request, "accounts/dashboard.html", {
        "packages": packages_ctx,
        "invoices": invoices_ctx,
        "account_manager": account_manager,
        "email_pending": email_pending,
        "verify_deadline": verify_deadline,
    })

        
   


# ---------------------------
# Customer actions
# ---------------------------

@login_required
@require_POST
def add_package(request):
    """
    Add a package for the current user by slug (form hidden input).
    Prevents duplicates unless prior one was canceled.
    """
    slug = (request.POST.get("slug") or "").strip()
    if not slug:
        messages.error(request, "No package selected.")
        return redirect("accounts:dashboard")

    try:
        pkg = PackageCatalog.objects.get(slug=slug)
    except PackageCatalog.DoesNotExist:
        messages.error(request, f"Package not found: “{slug}”.")
        return redirect("accounts:dashboard")

    exists = (
        UserPackage.objects
        .filter(user=request.user, package=pkg)
        .exclude(status="canceled")
        .first()
    )
    if exists:
        messages.info(request, f'You already have “{pkg.name}”.')
        return redirect("accounts:dashboard")

    UserPackage.objects.create(
        user=request.user,
        package=pkg,
        status="in_progress",
        step=0,
        paid_cents=0,
    )
    messages.success(request, f'Added “{pkg.name}”. Make the 30% deposit to begin.')
    return redirect("accounts:dashboard")


# Stripe Package Payment

stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
@require_POST
def pay_package(request, pk: int):
    """
    Start Stripe Checkout for the NEXT milestone (30/40/30) of this package.
    """
    up = get_object_or_404(UserPackage, pk=pk, user=request.user)
    next_due = int(up.next_partial_cents or 0)  # cents

    if next_due <= 0:
        messages.info(request, "No payment is due for this package.")
        return redirect("accounts:dashboard")

    label_by_step = {0: "Deposit (30%)", 1: "Design approval (40%)", 2: "Final (30%)", 3: "Complete"}
    label = label_by_step.get(up.step, "Milestone")

    # Build absolute success/cancel URLs (local dev is http)
    base = request.build_absolute_uri("/")[:-1]  # e.g. http://127.0.0.1:8000
    success_url = base + reverse("accounts:pay_success", args=[up.id]) + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url  = base + reverse("accounts:pay_cancel")

    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=(request.user.email or None),
        line_items=[{
            "quantity": 1,
            "price_data": {
                "currency": "usd",
                "unit_amount": next_due,     # cents
                "product_data": {
                    "name": f"{up.package.name} — {label}",
                },
            },
        }],
        success_url=success_url,
        cancel_url=cancel_url,
        allow_promotion_codes=False,
        automatic_tax={"enabled": False},
    )
    return redirect(session.url, permanent=False)


@login_required
def pay_success(request, pk: int):
    """
    After Stripe redirects back: verify session is paid, then record Payment and advance.
    """
    session_id = request.GET.get("session_id")
    if not session_id:
        messages.error(request, "Missing Stripe session.")
        return redirect("accounts:dashboard")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        messages.error(request, "Could not verify the payment. Please contact support.")
        return redirect("accounts:dashboard")

    if session.payment_status != "paid":
        messages.error(request, "Payment not completed.")
        return redirect("accounts:dashboard")

    up = get_object_or_404(UserPackage, pk=pk, user=request.user)
    amount = int(session.amount_total or 0)  # cents

    # Create a Payment and advance milestone
    Payment.objects.create(
        user=request.user,
        user_package=up,
        amount_cents=amount,
        status="paid",
    )

    up.apply_payment(amount)
    up.save()

    if up.status == "active":
        messages.success(request, f'Final payment received. “{up.package.name}” is now Active.')
    else:
        messages.success(request, "Payment received. Your project has advanced to the next step.")
    return redirect("accounts:dashboard")


@login_required
def pay_cancel(request):
    messages.info(request, "Payment canceled.")
    return redirect("accounts:dashboard")
 #end

# Stripe Maintenance Package Payement
# --- ADD near your other imports ---




# --- helper: map care slug -> price id (monthly) ---
CARE_PRICE_MAP = {
    "care-basic": settings.STRIPE_PRICE_CARE_BASIC,
    "care-plus":  settings.STRIPE_PRICE_CARE_PLUS,
    "care-pro":   settings.STRIPE_PRICE_CARE_PRO,
}

@login_required
@require_POST
def subscribe_care(request, slug):
    """
    Start a monthly subscription for care-basic / care-plus / care-pro via Stripe Checkout.
    - mode = 'subscription'
    - Uses user email (no manual customer creation needed)
    - On success, we’ll handle activation via webhook (recommended) or show a success page
    """
    price_id = CARE_PRICE_MAP.get(slug)
    if not price_id:
        messages.error(request, "Plan not found.")
        return redirect("accounts:dashboard")

    # Make sure the catalog item exists (optional but nice)
    try:
        pkg = PackageCatalog.objects.get(slug=slug)
    except PackageCatalog.DoesNotExist:
        messages.error(request, "Care plan not available.")
        return redirect("accounts:dashboard")

    # Ensure the user has a UserPackage row for this plan (create if missing)
    up, _created = UserPackage.objects.get_or_create(
        user=request.user,
        package=pkg,
        defaults={"status": "in_progress", "paid_cents": 0, "step": 0},
    )

    # Build success/cancel URLs
    success_url = request.build_absolute_uri(reverse("accounts:subscribe_success"))
    cancel_url  = request.build_absolute_uri(reverse("accounts:subscribe_cancel"))

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer_email=request.user.email,  # Stripe will create/fetch the Customer
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            allow_promotion_codes=True,
            automatic_tax={"enabled": False},
            # Attach app metadata so webhook can link back to your DB
            metadata={
                "user_id": str(request.user.id),
                "user_package_id": str(up.id),
                "package_slug": slug,
            },
        )
        return HttpResponseRedirect(session.url)
    except stripe.error.StripeError as e:
        messages.error(request, f"Stripe error: {str(e)}")
        return redirect("accounts:dashboard")


@login_required
def subscribe_success(request):
    """
    Lightweight success page. Real source of truth should be webhook events to flip statuses.
    """
    session_id = request.GET.get("session_id")
    if not session_id:
        messages.error(request, "Missing Stripe session.")
        return redirect("accounts:dashboard")

    try:
        # No expand needed here — Checkout Session already has what we need
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError as e:
        # You can keep this more detailed while developing
        log.exception("Stripe error retrieving checkout session")
        messages.error(
            request,
            f"Stripe error while verifying subscription: {getattr(e, 'user_message', None) or str(e)}"
        )
        return redirect("accounts:dashboard")

    # Make sure the payment actually completed
    if session.payment_status != "paid":
        messages.warning(
            request,
            "Your subscription is processing. It’ll activate once the payment clears."
        )
        return redirect("accounts:dashboard")

    # Metadata we attached when creating the Checkout Session
    meta = session.metadata or {}
    up_id = meta.get("user_package_id")
    if not up_id:
        messages.error(request, "Subscription metadata missing. Please contact support.")
        return redirect("accounts:dashboard")

    up = get_object_or_404(UserPackage, pk=int(up_id), user=request.user)

    # Primary way: use amount_total directly from the Checkout Session
    amount_cents = int(getattr(session, "amount_total", 0) or 0)

    # Optional fallback: try to derive from the subscription's latest invoice
    if amount_cents <= 0 and getattr(session, "subscription", None):
        try:
            # session.subscription is usually a string ID here
            sub = stripe.Subscription.retrieve(session.subscription)
            inv_id = getattr(sub, "latest_invoice", None)
            if inv_id:
                inv = stripe.Invoice.retrieve(inv_id)
                amount_cents = int(inv.amount_paid or inv.amount_due or 0)
        except stripe.error.StripeError:
            # If this fails, we just leave amount_cents as-is (0)
            pass

    # Record a Payment if we have a positive amount
    if amount_cents > 0:
        Payment.objects.create(
            user=request.user,
            user_package=up,
            amount_cents=amount_cents,
            status="paid",
        )

    # Flip the plan to active
    up.status = "active"
    up.save(update_fields=["status"])

    messages.success(request, "Your maintenance plan is active. Thank you!")
    return redirect("accounts:dashboard")



@login_required
def subscribe_cancel(request):
    messages.info(request, "Subscription was canceled before checkout completed.")
    return redirect("accounts:dashboard")


@login_required
def billing_portal(request):
    """
    Optional: open Stripe Billing Portal so the customer can manage payment methods/cancel.
    You must enable Billing Portal in Stripe Dashboard and set a return URL.
    """
    return_url = request.build_absolute_uri(reverse("accounts:dashboard"))
    try:
        # Create/fetch stripe customer by email
        customers = stripe.Customer.list(email=request.user.email).data
        customer_id = customers[0].id if customers else None
        if not customer_id:
            # If there’s no Stripe customer yet, just send them back
            messages.info(request, "No billing profile yet. Start a subscription first.")
            return redirect("accounts:dashboard")

        portal = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return HttpResponseRedirect(portal.url)
    except stripe.error.StripeError as e:
        messages.error(request, f"Stripe error: {str(e)}")
        return redirect("accounts:dashboard")


@login_required
@require_POST
def pause_plan(request, pk: int):
    """
    Pause only allowed for active plans.
    """
    up = get_object_or_404(UserPackage, pk=pk, user=request.user)
    if up.status == "active":
        up.status = "paused"
        up.save()
        messages.success(request, f'“{up.package.name}” has been paused.')
    else:
        messages.info(request, "Only active plans can be paused.")
    return redirect("accounts:dashboard")


@login_required
@require_POST
def cancel_plan(request, pk: int):
    """
    Cancel any non-canceled plan (marks it 'canceled'; user can then 'Remove').
    """
    up = get_object_or_404(UserPackage, pk=pk, user=request.user)
    if up.status != "canceled":
        up.status = "canceled"
        up.save()
        messages.success(request, f'“{up.package.name}” has been canceled.')
    else:
        messages.info(request, "This plan is already canceled.")
    return redirect("accounts:dashboard")


@login_required
@require_POST
def remove_plan(request, pk: int):
    """
    Permanently delete a *canceled* plan from the user's list.
    """
    up = get_object_or_404(UserPackage, pk=pk, user=request.user)
    if up.status != "canceled":
        messages.info(request, "Only canceled services can be removed.")
        return redirect("accounts:dashboard")
    name = up.package.name
    up.delete()
    messages.success(request, f"“{name}” has been removed from your services.")
    return redirect("accounts:dashboard")


@login_required
def reset_my_data(request):
    """
    Dev/test-only helper to clear this user's data.
    Consider removing this in production.
    """
    Payment.objects.filter(user=request.user).delete()
    UserPackage.objects.filter(user=request.user).delete()
    messages.warning(request, "All your services and payments were cleared.")
    return redirect("accounts:dashboard")


#staff aware
class StaffAwareLoginView(LoginView):
    """
    Overrides the success URL: staff → staff dashboard, otherwise customer.
    """
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if user.is_authenticated and (user.is_staff or user.groups.filter(name="staff").exists()):
            return reverse("accounts:staff_dashboard")
        return reverse("accounts:dashboard")

#Sign up
def signup(request):
    """
    Public customer signup:
    - Collects name, email, optional phone
    - Creates INACTIVE user
    - Sends a 24h verification link
    - Shows a 'check your email' page
    """
    if request.user.is_authenticated:
        messages.info(request, "You are already signed in.")
        return redirect("accounts:route_after_login")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            # Create inactive user
            user = form.save(commit=False)
            user.first_name = form.cleaned_data["first_name"].strip()
            user.last_name  = form.cleaned_data["last_name"].strip()
            user.email      = form.cleaned_data["email"].strip().lower()
            user.username   = user.email   
            user.is_active  = False
            user.save()

            # Ensure a CustomerAccount exists and store optional phone
            phone = form.cleaned_data.get("phone", "").strip()
            ca, _ = CustomerAccount.objects.get_or_create(customer=user)
            if phone:
                ca.phone = phone
                ca.save(update_fields=["phone"])

            # Build 24h activation link (token signed with timestamp)
            uid   = urlsafe_base64_encode(force_bytes(user.pk))
            token = signer.sign(str(user.pk))
            activate_url = request.build_absolute_uri(
                reverse("accounts:activate", args=[uid, token])
            )

            # Send email
            subject = "Verify your email to activate your BigSons account"
            body = render_to_string("accounts/email/activation_email.txt", {
                "user": user,
                "activate_url": activate_url,
            })
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)

            # Friendly confirmation page
            return render(
                request,
                "registration/activation_sent.html",
                {"email": user.email}
            )
    else:
        form = SignupForm()

    return render(request, "registration/signup.html", {"form": form})

#Contact us
def signup_issue_contact(request):
    """
    Simple support page for signup / account issues.
    Sends an email to BigSons and a confirmation email to the user.
    """
    if request.method == "POST":
        form = SignupIssueForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"].strip()
            email = form.cleaned_data["email"].strip()
            subject = form.cleaned_data["subject"].strip()
            message = form.cleaned_data["message"].strip()

            # Where you want to receive these support messages
            owner_email = getattr(settings, "SUPPORT_EMAIL", None) or getattr(settings, "DEFAULT_FROM_EMAIL", None) or "info@bigsonsweb.com"

            # 1) Email to you (BigSons)
            owner_subject = f"[Signup Issue] {subject}"
            owner_body = (
                f"New signup/account issue from BigSons site:\n\n"
                f"Name: {name}\n"
                f"Email: {email}\n\n"
                f"Message:\n{message}\n"
            )
            send_mail(
                owner_subject,
                owner_body,
                settings.DEFAULT_FROM_EMAIL,
                [owner_email],
                fail_silently=False,
            )

            # 2) Confirmation email to the user
            user_subject = "We received your signup issue – BigSons"
            user_body = (
                f"Hi {name},\n\n"
                "Thanks for reaching out about your signup or account issue.\n"
                "We’ve received your message and will review it as soon as possible.\n\n"
                "Here’s a copy of what you sent:\n"
                "----------------------------------------\n"
                f"{message}\n"
                "----------------------------------------\n\n"
                "If you need to add anything, you can simply reply to this email.\n\n"
                "— BigSons Web & Marketing"
            )
            send_mail(
                user_subject,
                user_body,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )

            messages.success(
                request,
                "Thanks! We’ve received your message and emailed you a confirmation."
            )
            # You can redirect to dashboard or login or stay on the page
            return redirect("accounts:signup_issue_contact")
    else:
        # Pre-fill name/email for logged-in users if available
        initial = {}
        if request.user.is_authenticated:
            full_name = (request.user.get_full_name() or "").strip()
            if full_name:
                initial["name"] = full_name
            if request.user.email:
                initial["email"] = request.user.email

        form = SignupIssueForm(initial=initial)

    return render(request, "accounts/signup_issue_contact.html", {"form": form})

def activate(request, uidb64, token):
    """
    Activates account if token valid and <=24h old.
    If expired, delete the inactive account.
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError):
        user = None

    if user is None:
        messages.error(request, "Invalid activation link.")
        return redirect("accounts:login")

    # If already active, just send to login
    if user.is_active:
        messages.success(request, "Your account is already verified. Please sign in.")
        return redirect("accounts:login")

    try:
        # Unsigned value must match user.pk; enforce 24h with max_age
        unsigned = signer.unsign(token, max_age=86400)  # 24 * 60 * 60
        if unsigned != str(user.pk):
            raise BadSignature("Token user mismatch.")
    except SignatureExpired:
        # Delete the pending account if not activated in time
        user.delete()
        messages.error(
            request,
            "Your verification link expired. Please sign up again to receive a new link."
        )
        return redirect("accounts:signup")
    except BadSignature:
        messages.error(request, "Invalid verification link.")
        return redirect("accounts:login")

    # Good token within 24h — activate
    user.is_active = True
    user.save(update_fields=["is_active"])
    messages.success(request, "Email verified! You can now sign in.")
    return redirect("accounts:login")

# Public: verify endpoint
def verify_email(request, token):
    try:
        evt = EmailVerificationToken.objects.select_related("user").get(token=token)
    except EmailVerificationToken.DoesNotExist:
        messages.error(request, "That verification link is invalid or has already been used.")
        return redirect("accounts:login")

    # expired?
    if evt.expires_at and evt.expires_at < timezone.now():
        # Optionally delete stale users here; we’ll handle cleanup via command below.
        evt.delete()
        messages.error(request, "That verification link has expired. Please request a new one.")
        return redirect("accounts:login")

    # mark verified
    user = evt.user
    ca, _ = CustomerAccount.objects.get_or_create(customer=user)
    if not ca.email_verified_at:
        ca.email_verified_at = timezone.now()
        ca.save(update_fields=["email_verified_at"])

    # remove all tokens for this user
    EmailVerificationToken.objects.filter(user=user).delete()

    messages.success(request, "Email verified — thanks! Your account is fully active.")
    return redirect("accounts:dashboard")

# Public: resend link (while pending)

@login_required
def resend_verification(request):
    ca, _ = CustomerAccount.objects.get_or_create(customer=request.user)
    if ca.email_verified_at:
        messages.info(request, "Your email is already verified.")
        return redirect("accounts:dashboard")

    evt = EmailVerificationToken.objects.create(user=request.user)
    verify_url = request.build_absolute_uri(
        reverse("accounts:verify_email", args=[str(evt.token)])
    )
    subject = "Your new BigSons verification link"
    body = (
        f"Hi {request.user.first_name or request.user.username},\n\n"
        "Here’s your fresh verification link (valid for 24 hours):\n\n"
        f"{verify_url}\n\n"
        "Thanks for helping keep your account secure.\n\n"
        "— BigSons Team"
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [request.user.email], fail_silently=False)
    messages.success(request, "We’ve sent you a new verification link.")
    return redirect("accounts:dashboard")
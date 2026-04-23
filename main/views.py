# main/views.py
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import SignupForm

from .forms import ContactForm
from .models import ContactMessage
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives

from django.http import HttpResponse
from datetime import date
from django.http import Http404
from django.template import loader, TemplateDoesNotExist
from django.contrib.staticfiles import finders

#payment
from django.views.decorators.http import require_POST
from django.http import HttpResponseBadRequest

#security
from django_ratelimit.decorators import ratelimit


User = get_user_model() # make sure this includes: username, first_name, last_name, phone, email, password1/2

User = get_user_model()

# ===============================
# SERVICES CATALOG (static for now)
# ===============================
SERVICES = [
    {
        "slug": "website-design",
        "name": "Website Design & Build",
        "blurb": "Custom, mobile-first websites built for speed, clarity, and conversions.",
        "icon": "bi-display",
        "image": "main/img/services/website-design.jpg",
        "features": [
            "Modern, mobile-first layouts",
            "Clean structure and messaging",
            "Fast loading (Core Web Vitals mindful)",
            "Lead capture (forms, CTAs, tracking)",
        ],
    },
    {
        "slug": "website-care",
        "name": "Website Care & Maintenance",
        "blurb": "Security updates, backups, uptime monitoring, and content edits handled for you.",
        "icon": "bi-shield-check",
        "image": "main/img/services/website-care.jpg",
        "features": [
            "Core & dependency updates",
            "Daily backups + restore support",
            "Uptime & security monitoring",
            "Minor monthly content edits",
        ],
    },
    {
        "slug": "seo-local",
        "name": "Local SEO Setup",
        "blurb": "Be found in Noblesville, Fishers, Carmel & Indianapolis when customers search.",
        "icon": "bi-geo-alt",
        "image": "main/img/services/seo-local.jpg",
        "features": [
            "Google Business Profile optimization",
            "Location/service pages + schema",
            "Review & keyword basics",
            "Search Console + Analytics setup",
        ],
    },
    {
        "slug": "managed-hosting",
        "name": "Managed Hosting",
        "blurb": "Fast, secure hosting with SSL, CDN and server-level caching.",
        "icon": "bi-cloud-check",
        "image": "main/img/services/hosting.jpg",
        "features": [
            "SSL, CDN, HTTP/2 or HTTP/3",
            "Server-level caching & monitoring",
            "DDoS/Firewall (provider-level)",
            "Staging environment (optional)",
        ],
    },
]

def _get_service(slug):
    return next((s for s in SERVICES if s["slug"] == slug), None)

# ===============================
# CORE PAGES
# ===============================
def home(request):
    return render(request, "main/home.html")

def services(request):
    return render(request, "main/services.html", {"services": SERVICES})

def service_detail(request, slug):
    svc = _get_service(slug)
    if not svc:
        return render(request, "main/404.html", status=404)
    return render(request, "main/service_detail.html", {"service": svc})

def about(request):
    return render(request, "main/about.html")

# Contact
@ratelimit(key='ip', rate='5/m', block=True)
def contact(request):
    selected_package = request.GET.get("package") or request.POST.get("package", "")

    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            cm = ContactMessage.objects.create(
                name=form.cleaned_data["name"].strip(),
                email=form.cleaned_data["email"].strip().lower(),
                phone=(form.cleaned_data.get("phone") or "").strip(),
                business_name=(form.cleaned_data.get("business_name") or "").strip(),
                interest=(form.cleaned_data.get("interest") or "").strip(),
                package=(form.cleaned_data.get("package") or "").strip(),
                message=form.cleaned_data["message"].strip(),
                seo_details=(form.cleaned_data.get("seo_details") or "").strip(),
            )

            # ---- Email to you (HTML + plain text) ----
            ctx = {"cm": cm, "request": request}
            subject_owner = f"[Contact] {cm.name} — {cm.interest or cm.package or 'New message'}"

            text_body = render_to_string("emails/contact_owner.txt", ctx)
            html_body = render_to_string("emails/contact_owner.html", ctx)

            to_list = getattr(settings, "CONTACT_NOTIFY_EMAILS", [settings.EMAIL_HOST_USER])
            msg = EmailMultiAlternatives(
                subject_owner,
                text_body,
                settings.DEFAULT_FROM_EMAIL,
                to_list,
                reply_to=[cm.email],
            )
            msg.attach_alternative(html_body, "text/html")
            msg.send(fail_silently=False)

            # ---- Auto-reply to customer (plain text) ----
            subject_user = "We received your message — BigSons Web & Marketing"
            user_text = render_to_string("emails/contact_autoreply.txt", ctx)
            send_mail(subject_user, user_text, settings.DEFAULT_FROM_EMAIL, [cm.email], fail_silently=True)

            messages.success(request, "Thanks! We’ve received your message and will get back to you shortly.")
            return redirect("main:contact")  # PRG pattern
    else:
        form = ContactForm(initial={"package": selected_package} if selected_package else None)

    return render(request, "main/contact.html", {
        "form": form,
        "selected_package": selected_package,
    })


def pricing(request):
    return render(request, "main/pricing.html")

# ===============================
# ---------- BLOG DATA ----------




# ===============================
# AUTH / DASHBOARDS
# ===============================
def login_view(request):
    next_url = request.GET.get("next", "")
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if next_url:
                return redirect(next_url)
            return redirect("accounts:staff_dashboard" if user.is_staff else "accounts:dashboard")
        # invalid → fall through; optionally add messages.error
    return render(request, "main/login.html", {"next": next_url})

@login_required
def customer_dashboard(request):
    sample_packages = [
        {"name": "Business Essentials", "status": "In progress", "price": "$1,499", "paid": "$450", "due": "$1,049"},
        {"name": "Care Plus (monthly)", "status": "Active", "price": "$79 / month", "paid": "$79", "due": "$0"},
    ]
    return render(request, "main/customer_dashboard.html", {"packages": sample_packages})

@login_required
def staff_dashboard(request):
    # If you’re actually using the accounts app’s staff dashboard, feel free to delete this.
    return render(request, "main/staff_dashboard.html")

# ===============================
# SIGNUP (verify-by-email, but allow login immediately)
# ===============================
@ratelimit(key='ip', rate='10/h', block=True)
def signup_view(request):
    """
    - Create ACTIVE user so they can log in immediately.
    - Generate a 24h email verification token (accounts.EmailVerificationToken).
    - Send verify email; show a 'pending' banner in accounts dashboard until verified.
    """
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            # Create ACTIVE user now (password set by UserCreationForm)
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"].strip().lower()
            user.first_name = form.cleaned_data.get("first_name", "").strip()
            user.last_name  = form.cleaned_data.get("last_name", "").strip()
            user.is_active  = True   # allow login right away
            user.save()

            # Optional phone → stash on CustomerAccount.notes (or dedicated phone field if you add one)
            phone = (form.cleaned_data.get("phone") or "").strip()
            try:
                from accounts.models import CustomerAccount, EmailVerificationToken
            except Exception:
                CustomerAccount = None
                EmailVerificationToken = None

            if CustomerAccount:
                ca, _ = CustomerAccount.objects.get_or_create(customer=user)
                if phone:
                    ca.notes = f"{(ca.notes + '\\n') if ca.notes else ''}Phone: {phone}"
                    ca.save(update_fields=["notes"])

            # Create verification token & send email (best-effort; don’t crash on SMTP issues in dev)
            if EmailVerificationToken:
                try:
                    evt = EmailVerificationToken.objects.create(user=user)
                    verify_url = request.build_absolute_uri(
                        reverse("accounts:verify_email", args=[str(evt.token)])
                    )
                    subject = "Please verify your BigSons account"
                    body = (
                        f"Hi {user.first_name or user.username},\n\n"
                        "Welcome to BigSons Web & Marketing! To keep your account secure, "
                        "please verify your email within 24 hours:\n\n"
                        f"{verify_url}\n\n"
                        "You can still explore your dashboard while it’s pending.\n\n"
                        "— BigSons Team"
                    )
                    send_mail(
                        subject,
                        body,
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                        fail_silently=False,
                    )
                except Exception as e:
                    # Don’t block signup if email fails in dev; show a gentle heads-up.
                    messages.warning(
                        request,
                        "Your account was created, but we couldn’t send the verification email right now."
                    )
            else:
                messages.warning(
                    request,
                    "Your account was created, but verification isn’t enabled yet."
                )

            # Log them in and show a friendly “pending” banner in dashboard
            login(request, user)
            messages.info(
                request,
                "We’ve emailed you a verification link. "
                "You can use the dashboard now, but some features may be limited until you confirm."
            )
            return redirect("accounts:dashboard")

        # invalid form → re-render with errors
        return render(request, "registration/signup.html", {"form": form})

    # GET → empty form
    return render(request, "registration/signup.html", {"form": SignupForm()})


# ---- Demo package catalog (replace with your real packages if you want) ----
# main/views.py (replace the demo PACKAGES with this)
PACKAGES = {
    "launch-starter": {
        "name": "Launch Starter",
        "price_display": "$799",
        "interval": "one-time",
        "description": "Clean 3–5 page site, fast build, essentials only.",
        "features": [
            "Up to 5 pages + contact form",
            "Mobile-first, fast load",
            "Basic on-page SEO",
            "HTTPS / security basics",
        ],
    },
    "business-essentials": {
        "name": "Business Essentials",
        "price_display": "$1,499",
        "interval": "one-time",
        "description": "Professional site with services, reviews, and CTAs that convert.",
        "features": [
            "7–10 pages + contact",
            "Local SEO structure",
            "Speed tuning",
            "Conversion-focused CTAs",
        ],
    },
    "growth-plus": {
        "name": "Growth Plus",
        "price_display": "$2,399",
        "interval": "one-time",
        "description": "Custom sections, blog, tracking, and strategy baked in.",
        "features": [
                "Custom sections & CTAs",
                "Blog & categories",
                "Form/Call tracking",
                "Quarterly strategy review",
        ],
    },
    "care-basic": {
        "name": "Care Basic",
        "price_display": "$39",
        "interval": "month",
        "description": "Updates, backups, uptime monitoring.",
        "features": [
            "Core/theme/plugin updates",
            "Daily backups",
            "Uptime monitoring",
        ],
    },
    "care-plus": {
        "name": "Care Plus",
        "price_display": "$79",
        "interval": "month",
        "description": "Everything in Basic plus performance tuning.",
        "features": [
            "All Care Basic",
            "Performance tweaks",
            "Minor content edits",
        ],
    },
    "care-pro": {
        "name": "Care Pro",
        "price_display": "$149",
        "interval": "month",
        "description": "Priority support and strategy.",
        "features": [
            "Priority support",
            "Quarterly strategy",
            "Expanded edits",
        ],
    },
}


def _resolve_package(key_or_name: str | None):
    if not key_or_name:
        return None
    q = key_or_name.strip().lower()
    # match by key (essentials/growth/pro) or by human name
    for slug, data in PACKAGES.items():
        if q == slug or q == data["name"].lower():
            return slug
    return None

def payments_dashboard(request):
    """
    Customer payment dashboard (demo). Accepts ?package=essentials|growth|pro or full name.
    Stores the selection in session so you can send them here from Pricing/Contact.
    """
    # Read selected package from querystring (preferred) or from session
    selected_qs = request.GET.get("package") or request.GET.get("plan")
    if selected_qs:
        slug = _resolve_package(selected_qs)
        if slug:
            request.session["selected_package"] = slug

    selected_slug = request.session.get("selected_package")
    selected = PACKAGES.get(selected_slug) if selected_slug else None

    # You could also list "open invoices" from your DB here. For now, just show packages.
    return render(
        request,
        "main/payments_dashboard.html",
        {
            "packages": PACKAGES,
            "selected_slug": selected_slug,
            "selected": selected,
        },
    )

@require_POST
def mock_checkout(request):
    """
    Demo checkout: pretends to 'pay' and redirects to success.
    Replace this later with Stripe Checkout session creation.
    """
    slug = request.POST.get("plan")
    pkg = PACKAGES.get(slug)
    if not pkg:
        return HttpResponseBadRequest("Unknown plan")

    # Save a tiny 'receipt' in session to show on the success page
    request.session["last_payment"] = {
        "plan": slug,
        "name": pkg["name"],
        "amount_display": f"${pkg['price']/100:,.2f} / {pkg['interval']}",
    }
    return redirect("payment_success")

def payment_success(request):
    info = request.session.get("last_payment") or {}
    return render(request, "main/payment_success.html", {"info": info})

def payment_cancelled(request):
    return render(request, "main/payment_cancelled.html")
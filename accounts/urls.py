# accounts/urls.py
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = "accounts"

# --- Optional custom login view ---------------------------------------------
# If you added `class StaffAwareLoginView(LoginView)` in views.py, we'll use it.
# If not, this try/except prevents import errors and we simply won't expose
# a custom login URL here (Django's default auth URLs can still be used).
try:
    from .views import StaffAwareLoginView
    CUSTOM_LOGIN = True
except Exception:
    CUSTOM_LOGIN = False




urlpatterns = [
    # -------------------------------------------------------------------------
    # Post-login router:
    # Every successful login should hit this first (set in settings.py):
    #     LOGIN_REDIRECT_URL = 'accounts:route_after_login'
    # It sends staff -> staff dashboard, others -> customer dashboard.
    # -------------------------------------------------------------------------
    path("route/", views.route_after_login, name="route_after_login"),

    # -------------------------------------------------------------------------
    # Customer area
    # -------------------------------------------------------------------------
    path("dashboard/", views.dashboard, name="dashboard"),

    # Package actions (customer self-service)
    path("packages/add/", views.add_package, name="add_package"),
    path("packages/<int:pk>/pause/", views.pause_plan, name="pause_plan"),
    path("packages/<int:pk>/cancel/", views.cancel_plan, name="cancel_plan"),
    path("packages/<int:pk>/remove/", views.remove_plan, name="remove_plan"),

    # Payments (simulate tranche payment)
    path("pay/<int:pk>/", views.pay_package, name="pay_package"),

    # Dev/test helper (clear current user's data) — remove for production
    path("reset-my-data/", views.reset_my_data, name="reset_my_data"),

    # -------------------------------------------------------------------------
    # Staff area (requires is_staff=True; guarded in views with @staff_member_required)
    # -------------------------------------------------------------------------
    path("staff/dashboard/", views.staff_dashboard, name="staff_dashboard"),
    path("staff/users/", views.staff_users_report, name="staff_users_report"),

    path("staff/tasks/<int:pk>/status/", views.staff_task_status, name="staff_task_status"),

    #sign up
    path("signup/", views.signup, name="signup"),
    path("activate/<uidb64>/<token>/", views.activate, name="activate"),

    # Email verification
    path("verify/<uuid:token>/", views.verify_email, name="verify_email"),
    path("verify/resend/", views.resend_verification, name="resend_verification"),
    path("login/", views.StaffAwareLoginView.as_view(), name="login"),
    
    # Stripe
    path("pay/<int:pk>/", views.pay_package, name="pay_package"),
    path("pay/success/<int:pk>/", views.pay_success, name="pay_success"),
    path("pay/cancel/", views.pay_cancel, name="pay_cancel"),

    # Care Plan subscription (Stripe Checkout - subscription)
    path("subscribe/care/<slug:slug>/", views.subscribe_care, name="subscribe_care"),
    path("subscribe/success/", views.subscribe_success, name="subscribe_success"),
    path("subscribe/cancel/", views.subscribe_cancel, name="subscribe_cancel"),

    # Optional: Stripe Billing Portal (to manage/cancel payment method)
    path("billing/portal/", views.billing_portal, name="billing_portal"),

    #Contact us
    path("signup-issue/", views.signup_issue_contact, name="signup_issue_contact"),
]
    



# If you defined the custom staff-aware login view, expose it at /accounts/login/
# (This will override the default auth login route if you also include it elsewhere.)
if CUSTOM_LOGIN:
    urlpatterns.insert(
        1,  # place near the top, right after the router
        path("login/", StaffAwareLoginView.as_view(), name="login"),
    )

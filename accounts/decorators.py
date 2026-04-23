# accounts/decorators.py
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

def _is_staff_user(user) -> bool:
    # Treat users in the "staff" group as staff (without granting Django admin).
    return user.is_authenticated and user.groups.filter(name="staff").exists()

def staff_required(view_func):
    """
    Only users who belong to the 'staff' group can enter.
    """
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if _is_staff_user(request.user):
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("Forbidden: staff only.")
    return _wrapped

def customer_required(view_func):
    """
    Customers = authenticated users NOT in the 'staff' group.
    """
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not _is_staff_user(request.user):
            return view_func(request, *args, **kwargs)
        # Staff trying to view customer pages? Send them to staff dashboard.
        return redirect("accounts:staff_dashboard")
    return _wrapped

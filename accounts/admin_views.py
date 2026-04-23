# accounts/admin_views.py
from datetime import date
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.template.response import TemplateResponse

from .models import Task

User = get_user_model()

def _is_superuser(u):  # hard-restrict to superusers only
    return u.is_active and u.is_superuser

@staff_member_required
@user_passes_test(_is_superuser)
def workload_dashboard(request):
    today = date.today()

    staff_qs = (
        User.objects
        .filter(is_staff=True)
        .order_by("username")
        .annotate(
            open_count=Count("assigned_tasks", filter=Q(assigned_tasks__status__in=["todo", "doing"])),
            due_today=Count("assigned_tasks", filter=Q(assigned_tasks__status__in=["todo", "doing"],
                                                       assigned_tasks__due_date=today)),
            overdue=Count("assigned_tasks", filter=Q(assigned_tasks__status__in=["todo", "doing"],
                                                     assigned_tasks__due_date__lt=today)),
            done_7d=Count("assigned_tasks", filter=Q(assigned_tasks__status="done")),
        )
    )

    # Top cards
    totals = {
        "open": Task.objects.filter(status__in=["todo", "doing"]).count(),
        "due_today": Task.objects.filter(status__in=["todo", "doing"], due_date=today).count(),
        "overdue": Task.objects.filter(status__in=["todo", "doing"], due_date__lt=today).count(),
        "done": Task.objects.filter(status="done").count(),
    }

    context = {
        "title": "Staff Workload",
        "staff_rows": staff_qs,
        "totals": totals,
        "site": request.current_site if hasattr(request, "current_site") else None,
    }
    return TemplateResponse(request, "admin/accounts/workload.html", context)

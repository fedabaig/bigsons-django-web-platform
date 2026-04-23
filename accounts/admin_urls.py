# accounts/admin_urls.py
from django.urls import path
from .admin_views import workload_dashboard

app_name = "accounts_admin"
urlpatterns = [
    path("workload/", workload_dashboard, name="workload"),
]

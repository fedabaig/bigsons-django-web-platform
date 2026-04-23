# main/urls.py
from django.urls import path, include
from django.urls import path
from . import views
from . import views as main_views 
app_name = 'main'

urlpatterns = [
    path('', views.home, name='home'),

    path('services/', views.services, name='services'),
    path('services/<slug:slug>/', views.service_detail, name='service_detail'),

    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),

   
    # dashboards:
    path('dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('staff/dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('pricing/', views.pricing, name='pricing'),

#Payment
    path("dashboard/payments/", views.payments_dashboard, name="payments_dashboard"),
    path("dashboard/payments/mock-checkout/", views.mock_checkout, name="mock_checkout"),
    path("dashboard/payments/success/", views.payment_success, name="payment_success"),
    path("dashboard/payments/cancelled/", views.payment_cancelled, name="payment_cancelled"),

   
]

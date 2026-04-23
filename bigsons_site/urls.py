# bigsons_site/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts import views as accounts_views 

from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
from blog.sitemaps import BlogPostSitemap
#blog
sitemaps = {"blog": BlogPostSitemap}


urlpatterns = [
    path("feda-admin/", admin.site.urls),

    # Public site (home, services, pricing, blog, contact, about)
    path("", include(("main.urls", "main"), namespace="main")),

    # Your custom accounts app (ONLY custom stuff like signup, dashboard)
   path("accounts/", include(("accounts.urls", "accounts"), namespace="accounts")),  # ← required

    # Django built-in auth views (login, logout, password reset, etc.)
    # Do NOT redefine these in accounts.urls
    path("accounts/", include("django.contrib.auth.urls")),

    

    #new blog
    
    # blog:
    path("blog/", include(("blog.urls", "blog"), namespace="blog")),
    # sitemap:
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    # robots.txt (simple)
    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt", content_type="text/plain"
        ),
        name="robots",
    ),
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
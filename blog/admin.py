# blog/admin.py
from django.contrib import admin
from .models import BlogPost

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "author_name", "is_published", "published_at")
    list_filter = ("is_published", "published_at")
    search_fields = ("title", "excerpt", "body", "author_name")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"

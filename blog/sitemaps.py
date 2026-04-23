# blog/sitemaps.py
from django.contrib.sitemaps import Sitemap
from .models import BlogPost

class BlogPostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return BlogPost.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at

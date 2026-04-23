# main/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

class StaticViewSitemap(Sitemap):
    priority = 0.9
    changefreq = "monthly"

    def items(self):
        return [
            "main:home",
            "main:services",
            "main:about",
            "main:contact",
            "main:pricing",
        ]

    def location(self, item):
        return reverse(item)

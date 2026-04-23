from django.db import models

class ContactMessage(models.Model):
    name          = models.CharField(max_length=150)
    email         = models.EmailField()
    phone         = models.CharField(max_length=30, blank=True)
    business_name = models.CharField(max_length=200, blank=True)
    interest      = models.CharField(max_length=100, blank=True)
    package       = models.CharField(max_length=120, blank=True)   # from ?package=... or hidden field
    message       = models.TextField()
    seo_details   = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    replied       = models.BooleanField(default=False)

    def __str__(self):
        topic = self.interest or self.package or "Contact"
        return f"{self.name} – {topic} ({self.created_at:%Y-%m-%d})"

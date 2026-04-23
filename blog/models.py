# blog/models.py
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, help_text="Used in the URL.")
    excerpt = models.TextField(max_length=350, help_text="Short preview text for cards and SEO.")
    body = models.TextField(help_text="You can paste HTML or plain text.")
    cover = models.ImageField(upload_to="blog_covers/", blank=True, null=True)
    author_name = models.CharField(max_length=120, default="BigSons Team")
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [models.Index(fields=["slug"])]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog:detail", args=[self.slug])

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:220]
        super().save(*args, **kwargs)

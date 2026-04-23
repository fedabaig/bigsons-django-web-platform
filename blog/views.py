# blog/views.py
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.templatetags.static import static
from .models import BlogPost

DEFAULT_COVER = "main/img/blog/default.jpg"  # create this file in /static

def _cover_url(post):
    if post.cover:
        return post.cover.url
    # static fallback
    return static(DEFAULT_COVER)

def list_view(request):
    posts = BlogPost.objects.filter(is_published=True)
    for p in posts:
        p.cover_url = _cover_url(p)
    abs_url = request.build_absolute_uri(request.path)
    return render(request, "blog/blog_list.html", {"posts": posts, "abs_url": abs_url})

def detail_view(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)
    post.cover_url = _cover_url(post)
    abs_url = request.build_absolute_uri(post.get_absolute_url())
    # very rough reading time (optional)
    word_count = len(post.body.split())
    reading = max(1, word_count // 225)
    return render(
        request,
        "blog/blog_detail.html",
        {"post": post, "abs_url": abs_url, "reading": f"{reading} min read"},
    )

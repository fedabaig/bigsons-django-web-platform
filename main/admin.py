from django.contrib import admin
from .models import ContactMessage

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "interest", "package", "created_at", "replied")
    list_filter = ("replied", "created_at", "interest")
    search_fields = ("name", "email", "business_name", "interest", "package", "message", "seo_details")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    actions = ["mark_replied"]

    @admin.action(description="Mark selected as replied")
    def mark_replied(self, request, qs):
        updated = qs.update(replied=True)
        self.message_user(request, f"Marked {updated} message(s) as replied.")

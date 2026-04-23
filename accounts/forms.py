# accounts/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.forms import HiddenInput

User = get_user_model()

class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True, max_length=150)
    last_name  = forms.CharField(required=True, max_length=150)
    phone      = forms.CharField(required=False, max_length=30)

    class Meta:
        model = User
        # keep username in Meta so ModelForm knows about it, but we’ll hide+autofill it
        fields = ("username", "email", "first_name", "last_name", "phone", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # hide username and make it non-required; we’ll set it from email
        if "username" in self.fields:
            self.fields["username"].required = False
            self.fields["username"].widget = HiddenInput()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data["email"].strip().lower()
        user.email = email
        user.username = email  # ← critical: login form labels “Email”, but Django expects username
        user.first_name = self.cleaned_data.get("first_name", "").strip()
        user.last_name  = self.cleaned_data.get("last_name", "").strip()
        user.is_active = False  # activation flow

        if commit:
            user.save()
            # store phone on CustomerAccount.phone (you already have that field)
            from accounts.models import CustomerAccount
            ca, _ = CustomerAccount.objects.get_or_create(customer=user)
            phone = (self.cleaned_data.get("phone") or "").strip()
            if phone:
                ca.phone = phone
                ca.save(update_fields=["phone"])
        return user

class SignupIssueForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        label="Your name",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Jane Doe"})
    )
    email = forms.EmailField(
        label="Your email",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"})
    )
    subject = forms.CharField(
        max_length=150,
        label="Subject",
        initial="Signup issue with my BigSons account",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    message = forms.CharField(
        label="Describe your issue",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 5,
            "placeholder": "Tell us what’s going wrong so we can help quickly..."
        })
    )
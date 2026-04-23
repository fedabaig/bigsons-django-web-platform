# main/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

User = get_user_model()

class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    phone = forms.CharField(max_length=30, required=False)  # optional

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name", "phone", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email
def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].strip().lower()
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        if commit:
            user.save()
        return user

#Contact


class ContactForm(forms.Form):
    name    = forms.CharField(max_length=150)
    email   = forms.EmailField()
    phone   = forms.CharField(max_length=30, required=False)
    business_name = forms.CharField(max_length=200, required=False)
    interest = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Please choose one"),
            ("New website", "New website"),
            ("Redesign of existing website", "Redesign of existing website"),
            ("Website maintenance & care", "Website maintenance & care"),
            ("Not sure yet / need guidance", "Not sure yet / need guidance"),
        ],
    )
    package = forms.CharField(max_length=120, required=False)   # will be hidden if preselected
    message = forms.CharField(widget=forms.Textarea, max_length=4000)
    seo_details = forms.CharField(widget=forms.Textarea, required=False, max_length=4000)

    # Honeypot (hidden)
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise ValidationError("Spam detected.")
        return ""

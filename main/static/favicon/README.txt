BigSons favicon pack

Put the 'favicon' folder under your Django app static directory, e.g.:
main/static/favicon/

Then add this to your base.html <head>:

{% load static %}
<link rel="icon" href="{% static 'favicon/favicon.ico' %}">
<link rel="icon" type="image/png" sizes="32x32" href="{% static 'favicon/favicon-32.png' %}">
<link rel="icon" type="image/png" sizes="96x96" href="{% static 'favicon/favicon-96.png' %}">
<link rel="apple-touch-icon" sizes="180x180" href="{% static 'favicon/apple-touch-icon.png' %}">

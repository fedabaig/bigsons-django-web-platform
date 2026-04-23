# BigSons Web Platform

A full-stack Django web application developed for a web design and digital services business. This platform is designed to support business operations through secure user management, content publishing, search engine optimization, and integrated online payment functionality.

---

## Overview

BigSons Web Platform is a production-style web application built to demonstrate practical software engineering skills in a real-world business context. The project emphasizes clean architecture, modular design, secure configuration, and maintainability.

It includes essential business-facing functionality such as authentication, blog management, contact communication, SEO support, and Stripe-based payment integration.

---

## Objectives

This project was developed to:

- Build a scalable web application using Django
- Apply secure configuration practices with environment variables
- Integrate third-party services such as Stripe and email delivery
- Organize application logic using a modular Django structure
- Create a portfolio-quality software project with real business relevance

---

## Technology Stack

### Backend
- Python
- Django

### Frontend
- HTML
- CSS
- JavaScript

### Database
- SQLite (development)
- PostgreSQL (optional for production)

### Integrations
- Stripe API
- SMTP email service (Zoho Mail)

### Deployment / Configuration
- WhiteNoise
- Environment-based settings
- Django security middleware

---

## Core Features

- **User Authentication**
  - Login, logout, and account-related functionality
  - Secure session handling

- **Blog Management**
  - Publish and manage blog content
  - SEO-friendly page structure
  - Sitemap support

- **Payment Integration**
  - Stripe integration for service plan payments
  - Secure handling of payment-related configuration

- **Contact and Communication**
  - Contact form functionality
  - Email notification support

- **Environment-Based Configuration**
  - Separate development and production behavior
  - Sensitive values managed through environment variables

- **Security Enhancements**
  - CSRF protection
  - HTTPS-related settings
  - Content Security Policy support
  - Secure cookie configuration

- **Modular Architecture**
  - Clear separation of application components
  - Reusable and maintainable project structure

---
## Run on Your PC (Local Development)

1. Clone the github Repository:
   ```bash
   git clone https://github.com/fbigzad/Bravo-Team.git
2. Enter the Project Folder:
   ```bash
   cd bigsons-django-web-platform
3. create a virtual Environment
   ```bash
   python -m venv venv
   venv\Scripts\Activate
4. Open `settings.py` file to change `DEBUG` value for local development
   - Path: `bigsons_site/settings.py`
5. Set `DEBUG` value to `True` for local development
   - `DEBUG = True`
   - Click **Save**
5. Install requirements.txt
   ```bash
   pip install -r requirements.txt
6. Run migrations (creates database tables)
   ```bash
   python manage.py migrate
7. Create admin user (optional)
	```bash
	python manage.py createsuperuser
8. Start the Django server
   ```bash
   python manage.py runserver

---

## Project Structure

```text
bigsons_site/      Core project configuration
accounts/          Authentication and user-related functionality
blog/              Blog and content management
main/              Core pages and business logic
templates/         HTML templates
static/            CSS, JavaScript, and image assets
manage.py          Django management entry point
requirements.txt   Project dependencies




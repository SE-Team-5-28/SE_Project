from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .permissions import role_required
from .models import User


def login_page(request):
    return render(request, "core/login.html")


@login_required
def dashboard(request):
    return render(request, "core/dashboard.html")


@role_required(User.Role.STUDENT)
def student_dashboard(request):
    return render(
        request,
        "core/role_dashboard.html",
        {"page_title": "Student Dashboard"},
    )


@role_required(User.Role.WARDEN)
def warden_dashboard(request):
    return render(
        request,
        "core/role_dashboard.html",
        {"page_title": "Warden Dashboard"},
    )


@role_required(User.Role.HOSTEL_ADMIN, User.Role.SYSTEM_ADMIN)
def administrator_dashboard(request):
    return render(
        request,
        "core/role_dashboard.html",
        {"page_title": "Administrator Dashboard"},
    )
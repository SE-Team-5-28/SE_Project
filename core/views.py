from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def login_page(request):
    return render(request, "core/login.html")


@login_required
def dashboard(request):
    return render(request, "core/dashboard.html")
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="core/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path("", views.dashboard, name="dashboard"),
    path(
        "role/student/",
        views.student_dashboard,
        name="student_dashboard",
    ),
    path(
        "role/warden/",
        views.warden_dashboard,
        name="warden_dashboard",
    ),
    path(
        "role/administrator/",
        views.administrator_dashboard,
        name="administrator_dashboard",
    ),
]
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="core/login.html"
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "", views.dashboard, name="dashboard"
    ),
    path(
        "students/", views.student_list, name="student_list"
    ),
    path(
        "students/add/", views.student_create, name="student_create"
    ),
    path(
        "students/<int:pk>/edit/", views.student_update, name="student_update"
    ),
]
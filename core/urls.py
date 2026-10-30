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
    path("hostels/", views.hostel_list, name="hostel_list"),
    path("hostels/add/", views.hostel_create, name="hostel_create"),
    path("blocks/add/", views.block_create, name="block_create"),
    path("rooms/add/", views.room_create, name="room_create"),
    path("allocations/", views.allocation_list, name="allocation_list"),
    path("allocations/add/", views.allocation_create, name="allocation_create"),
    path("transfers/", views.transfer_list, name="transfer_list"),
    path("transfers/add/", views.transfer_create, name="transfer_create"),
    path(
        "transfers/<int:pk>/<str:decision>/",
        views.transfer_review,
        name="transfer_review",
    ),
]

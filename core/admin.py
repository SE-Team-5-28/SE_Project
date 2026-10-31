from django.contrib import admin

from .forms import AllocationForm
from .models import (
    Allocation,
    AuditLog,
    Block,
    Complaint,
    Hostel,
    Room,
    Student,
    TransferRequest,
    UserRole,
)


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    form = AllocationForm


admin.site.register([Hostel, Block, Room, TransferRequest, AuditLog, Complaint])


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "student_id",
        "user",
        "department",
        "year_of_study",
    )
    search_fields = ("student_id", "user__username", "phone")
    list_filter = ("department", "year_of_study")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__username",)

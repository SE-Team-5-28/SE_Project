
from django.contrib import admin

from .models import Allocation, AuditLog, Block, Hostel, Room, Student, TransferRequest


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "model_name", "object_id")
    list_filter = ("action", "model_name")
    search_fields = ("object_id", "actor__username")
    readonly_fields = ("actor", "action", "model_name", "object_id", "details", "created_at")


admin.site.register([Hostel, Block, Room, Allocation, TransferRequest])


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "student_id",
        "full_name",
        "hostel_name",
        "room_number",
    )
    search_fields = ("student_id", "full_name")
    list_filter = ("hostel_name",)

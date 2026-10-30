from django.contrib import admin

from .models import Allocation, AuditLog, Block, Hostel, Room, Student, TransferRequest

# Registering AuditLog dynamically prevents hardcoded field errors
admin.site.register([Hostel, Block, Room, Allocation, TransferRequest, AuditLog])


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

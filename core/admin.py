
from django.contrib import admin
from .models import Student


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

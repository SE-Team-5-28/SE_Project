
from django.db import models


class Student(models.Model):
    student_id = models.CharField(
        max_length=30,
        unique=True,
        db_index=True
    )
    full_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    hostel_name = models.CharField(max_length=100)
    room_number = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student_id"]

    def __str__(self):
        return f"{self.student_id} - {self.full_name}"

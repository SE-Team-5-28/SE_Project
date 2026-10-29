from django import forms
from .models import Student


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            "student_id",
            "full_name",
            "email",
            "phone",
            "hostel_name",
            "room_number",
        ]
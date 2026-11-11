
import re

from django import forms
from django.core.validators import RegexValidator

from .models import (
    Allocation,
    Block,
    Complaint,
    Hostel,
    Room,
    Student,
    TransferRequest,
)


student_id_validator = RegexValidator(
    regex=r"^[A-Za-z0-9_-]{2,30}$",
    message="Student ID must contain only letters, numbers, hyphens or underscores.",
)

phone_validator = RegexValidator(
    regex=r"^[0-9+\- ]{7,20}$",
    message="Enter a valid phone number.",
)

room_code_validator = RegexValidator(
    regex=r"^[A-Za-z0-9_-]{2,50}$",
    message="Room code must contain only letters, numbers, hyphens or underscores.",
)


class StudentForm(forms.ModelForm):
    student_id = forms.CharField(
        max_length=30,
        validators=[student_id_validator],
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        validators=[phone_validator],
    )

    class Meta:
        model = Student
        fields = [
            "user", "student_id", "full_name", "email", "phone",
            "hostel_name", "room_number", "department", "year_of_study",
        ]

    def clean_full_name(self):
        value = self.cleaned_data["full_name"].strip()
        if value and not re.fullmatch(r"[A-Za-z][A-Za-z .'-]*", value):
            raise forms.ValidationError("Enter a valid student name.")
        return value


class HostelForm(forms.ModelForm):
    class Meta:
        model = Hostel
        fields = ["name", "address"]

    def clean_name(self):
        value = self.cleaned_data["name"].strip()
        if not value:
            raise forms.ValidationError("Hostel name cannot be empty.")
        return value


class BlockForm(forms.ModelForm):
    class Meta:
        model = Block
        fields = ["hostel", "name", "description"]

    def clean_name(self):
        value = self.cleaned_data["name"].strip()
        if not value:
            raise forms.ValidationError("Block name cannot be empty.")
        return value


class RoomForm(forms.ModelForm):
    room_code = forms.CharField(
        max_length=50,
        validators=[room_code_validator],
    )

    class Meta:
        model = Room
        fields = ["block", "number", "room_code", "capacity", "description"]

    def clean_number(self):
        value = self.cleaned_data["number"].strip()

        if not value:
            raise forms.ValidationError("Room number cannot be empty.")

        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise forms.ValidationError(
                "Room number must contain only letters, numbers, hyphens or underscores."
            )

        return value


class AllocationForm(forms.ModelForm):
    class Meta:
        model = Allocation
        fields = ["student", "room"]

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get("student")
        room = cleaned.get("room")

        if (
            student
            and Allocation.objects.filter(
                student=student,
                status=Allocation.Status.ACTIVE,
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            self.add_error(
                "student",
                "This student already has an active allocation.",
            )

        if room:
            occupied = Allocation.objects.filter(
                room=room,
                status=Allocation.Status.ACTIVE,
            ).exclude(pk=self.instance.pk).count()

            if occupied >= room.capacity:
                self.add_error(
                    "room",
                    f"This room is full ({occupied}/{room.capacity} occupants).",
                )

        return cleaned


class TransferRequestForm(forms.ModelForm):
    reason = forms.CharField(
        max_length=1000,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    class Meta:
        model = TransferRequest
        fields = ["requested_room", "reason"]

    def __init__(self, *args, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        self.fields["requested_room"].queryset = Room.objects.all()
        self.fields["requested_room"].required = True

    def clean_reason(self):
        value = self.cleaned_data["reason"]
        if len(value) < 5:
            raise forms.ValidationError(
                "Please provide a reason of at least 5 characters."
            )
        return value

    def clean_requested_room(self):
        room = self.cleaned_data["requested_room"]

        if room is None:
            return room

        occupied = Allocation.objects.filter(
            room=room,
            status=Allocation.Status.ACTIVE,
        ).count()

        if occupied >= room.capacity:
            raise forms.ValidationError("That room is currently full.")

        current = (
            self.student.allocations.filter(
                status=Allocation.Status.ACTIVE,
            ).first()
            if self.student
            else None
        )

        if current and current.room_id == room.id:
            raise forms.ValidationError(
                "Choose a room different from your current room."
            )

        return room


class ComplaintForm(forms.ModelForm):
    category = forms.CharField(max_length=100, strip=True)
    description = forms.CharField(
        strip=True,
        widget=forms.Textarea(attrs={"rows": 5}),
    )

    class Meta:
        model = Complaint
        fields = ["category", "description"]


class ComplaintUpdateForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ["status", "remarks"]
        widgets = {
            "remarks": forms.Textarea(attrs={"rows": 5}),
        }

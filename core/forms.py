from django import forms
from .models import Allocation, Block, Hostel, Room, Student, TransferRequest


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            "user",
            "student_id",
            "full_name",
            "email",
            "phone",
            "hostel_name",
            "room_number",
        ]


class HostelForm(forms.ModelForm):
    class Meta:
        model = Hostel
        fields = ["name", "address"]


class BlockForm(forms.ModelForm):
    class Meta:
        model = Block
        fields = ["hostel", "name"]


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["block", "number", "capacity"]


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
                is_active=True,
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            self.add_error("student", "This student already has an active allocation.")

        if room:
            occupied = Allocation.objects.filter(
                room=room,
                is_active=True,
            ).exclude(pk=self.instance.pk).count()
            if occupied >= room.capacity:
                self.add_error("room", "This room has no available space.")
        return cleaned


class TransferRequestForm(forms.ModelForm):
    class Meta:
        model = TransferRequest
        fields = ["requested_room", "reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        self.fields["requested_room"].queryset = Room.objects.all()

    def clean_requested_room(self):
        room = self.cleaned_data["requested_room"]

        occupied = Allocation.objects.filter(
            room=room,
            is_active=True,
        ).count()
        if occupied >= room.capacity:
            raise forms.ValidationError("That room is currently full.")

        current = (
            self.student.allocations.filter(is_active=True).first()
            if self.student
            else None
        )
        if current and current.room_id == room.id:
            raise forms.ValidationError("Choose a room different from your current room.")
        return room

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Allocation, Room, Student


@transaction.atomic
def allocate_student(student_id: int, room_id: int) -> Allocation:
    """Allocate a student without exceeding room capacity."""

    try:
        room = Room.objects.select_for_update().get(pk=room_id)
    except Room.DoesNotExist as exc:
        raise ValidationError("The requested room does not exist.") from exc

    try:
        student = Student.objects.select_for_update().get(pk=student_id)
    except Student.DoesNotExist as exc:
        raise ValidationError("The requested student does not exist.") from exc

    if Allocation.objects.filter(
        student=student,
        is_active=True,
    ).exists():
        raise ValidationError(
            "This student already has an active allocation."
        )

    occupied = Allocation.objects.filter(
        room=room,
        is_active=True,
    ).count()

    if occupied >= room.capacity:
        raise ValidationError("This room is already at full capacity.")

    try:
        # The inner atomic block creates a savepoint. If the database
        # rejects the insert, Django can roll back to this savepoint.
        with transaction.atomic():
            return Allocation.objects.create(
                student=student,
                room=room,
                is_active=True,
            )
    except IntegrityError as exc:
        raise ValidationError(
            "The allocation conflicts with an existing active allocation."
        ) from exc
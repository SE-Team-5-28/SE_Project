from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

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
        status=Allocation.Status.ACTIVE,
    ).exists():
        raise ValidationError(
            "This student already has an active allocation."
        )

    occupied = Allocation.objects.filter(
        room=room,
        status=Allocation.Status.ACTIVE,
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
                status=Allocation.Status.ACTIVE,
                check_in_date=timezone.localdate(),
            )
    except IntegrityError as exc:
        raise ValidationError(
            "The allocation conflicts with an existing active allocation."
        ) from exc


@transaction.atomic
def transfer_student(student_id: int, room_id: int) -> Allocation:
    """Move a student's active allocation without exposing partial state."""

    try:
        room = Room.objects.select_for_update().get(pk=room_id)
    except Room.DoesNotExist as exc:
        raise ValidationError("The requested room does not exist.") from exc

    try:
        student = Student.objects.select_for_update().get(pk=student_id)
    except Student.DoesNotExist as exc:
        raise ValidationError("The requested student does not exist.") from exc

    old_allocation = (
        Allocation.objects.select_for_update()
        .filter(student=student, status=Allocation.Status.ACTIVE)
        .first()
    )
    occupied = Allocation.objects.filter(
        room=room,
        status=Allocation.Status.ACTIVE,
    ).count()
    if occupied >= room.capacity:
        raise ValidationError("This room is already at full capacity.")

    if old_allocation:
        old_allocation.status = Allocation.Status.COMPLETED
        old_allocation.check_out_date = timezone.localdate()
        old_allocation.save(
            update_fields=[
                "status",
                "check_out_date",
                "active_student_guard",
                "is_active",
            ]
        )

    return allocate_student(student_id=student.pk, room_id=room.pk)
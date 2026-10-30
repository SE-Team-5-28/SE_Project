import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Student(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profile",
    )
    student_id = models.CharField(max_length=30, unique=True, db_index=True)
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


class Hostel(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address = models.CharField(max_length=255, blank=True)
    warden = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_hostels",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Block(models.Model):
    hostel = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name="blocks",
    )
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ["hostel__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["hostel", "name"],
                name="unique_block_per_hostel",
            ),
        ]

    def __str__(self):
        return f"{self.hostel.name} - {self.name}"


class Room(models.Model):
    block = models.ForeignKey(
        Block,
        on_delete=models.CASCADE,
        related_name="rooms",
    )
    number = models.CharField(max_length=20)
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    class Meta:
        ordering = ["block__hostel__name", "block__name", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["block", "number"],
                name="unique_room_per_block",
            ),
            models.CheckConstraint(
                condition=Q(capacity__gte=1),
                name="room_capacity_at_least_one",
            ),
        ]

    @property
    def occupied_count(self):
        return self.allocations.filter(is_active=True).count()

    @property
    def available_spaces(self):
        return max(self.capacity - self.occupied_count, 0)

    def __str__(self):
        return f"{self.block} / {self.number}"


class Allocation(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    allocated_at = models.DateTimeField(auto_now_add=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    active_student_guard = models.OneToOneField(
        Student,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        ordering = ["room", "student__student_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(is_active=True),
                name="one_active_allocation_per_student",
            ),
        ]

    def save(self, *args, **kwargs):
        self.active_student_guard_id = (
            self.student_id if self.is_active else None
        )
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                "active_student_guard",
            }
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.student_id} -> {self.room}"


class TransferRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="transfer_requests",
    )
    requested_room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="transfer_requests",
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    review_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_transfer_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Complaint(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    reference = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name="complaints",
    )
    category = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.OPEN,
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.reference)

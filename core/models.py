
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Student(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_profile",
    )
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
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="blocks")
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ["hostel__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["hostel", "name"], name="unique_block_per_hostel")
        ]

    def __str__(self):
        return f"{self.hostel.name} - {self.name}"


class Room(models.Model):
    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name="rooms")
    number = models.CharField(max_length=20)
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["block__hostel__name", "block__name", "number"]
        constraints = [
            models.UniqueConstraint(fields=["block", "number"], name="unique_room_per_block")
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
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="allocations")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="allocations")
    allocated_at = models.DateTimeField(auto_now_add=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["room", "student__student_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(is_active=True),
                name="one_active_allocation_per_student",
            )
        ]

    def __str__(self):
        return f"{self.student.student_id} -> {self.room}"


class TransferRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="transfer_requests")
    requested_room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="transfer_requests")
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
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

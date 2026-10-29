import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class User(AbstractUser):
    """HMS user with a role."""

    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        WARDEN = "WARDEN", "Warden"
        HOSTEL_ADMIN = "HOSTEL_ADMIN", "Hostel Administrator"
        SYSTEM_ADMIN = "SYSTEM_ADMIN", "System Administrator"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Student(models.Model):
    """Student's hostel-related profile."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_profile",
    )
    student_id = models.CharField(max_length=30, unique=True)
    phone = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True)
    year_of_study = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.student_id


class Hostel(models.Model):
    """A hostel managed by the institution."""

    name = models.CharField(max_length=100, unique=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Block(models.Model):
    """A block within a hostel."""

    hostel = models.ForeignKey(
        Hostel,
        on_delete=models.PROTECT,
        related_name="blocks",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["hostel", "name"],
                name="unique_block_name_per_hostel",
            ),
        ]

    def __str__(self):
        return f"{self.hostel.name} - {self.name}"


class Room(models.Model):
    """A room within a block."""

    block = models.ForeignKey(
        Block,
        on_delete=models.PROTECT,
        related_name="rooms",
    )
    room_number = models.CharField(max_length=20)
    room_code = models.CharField(max_length=50, unique=True)
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["block", "room_number"],
                name="unique_room_number_per_block",
            ),
            models.CheckConstraint(
                condition=Q(capacity__gte=1),
                name="room_capacity_at_least_one",
            ),
        ]

    def __str__(self):
        return f"{self.block} - Room {self.room_number}"


class Allocation(models.Model):
    """A student's room allocation and stay record."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    allocation_date = models.DateField(auto_now_add=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    check_in_date = models.DateField(null=True, blank=True)
    check_out_date = models.DateField(null=True, blank=True)

    # MySQL-compatible database guard for one active allocation per student.
    # Active records point this field to their student; historical records
    # leave it NULL. The OneToOneField enforces uniqueness in the database.
    active_student_guard = models.OneToOneField(
        Student,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["room", "status"],
                name="allocation_room_status_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.status == self.Status.ACTIVE:
            self.active_student_guard = self.student
        else:
            self.active_student_guard = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.student_id} - {self.room}"


class TransferRequest(models.Model):
    """A student's request to transfer rooms."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name="transfer_requests",
    )
    requested_room = models.ForeignKey(
        Room,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transfer_requests",
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transfer_decisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Transfer #{self.pk} - {self.status}"


class Complaint(models.Model):
    """A complaint submitted by a student."""

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


class AuditLog(models.Model):
    """Records important actions performed in the HMS."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} - {self.timestamp}"
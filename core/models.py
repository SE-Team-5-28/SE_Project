import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class UserRole(models.Model):
    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        WARDEN = "WARDEN", "Warden"
        HOSTEL_ADMIN = "HOSTEL_ADMIN", "Hostel Administrator"
        SYSTEM_ADMIN = "SYSTEM_ADMIN", "System Administrator"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="role_profile",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class _RoleAwareUserManager:
    def create_user(self, username, email=None, password=None, **extra_fields):
        role = extra_fields.pop("role", None)
        user = get_user_model()._default_manager.create_user(
            username=username,
            email=email,
            password=password,
            **extra_fields,
        )
        if role is None:
            role = (
                UserRole.Role.WARDEN
                if user.is_staff
                else UserRole.Role.STUDENT
            )
        if role not in UserRole.Role.values:
            raise ValueError(f"Unknown user role: {role}")
        set_user_role(user, role)
        user.role = role
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.pop("role", None)
        user = get_user_model()._default_manager.create_superuser(
            username=username,
            email=email,
            password=password,
            **extra_fields,
        )
        set_user_role(user, UserRole.Role.SYSTEM_ADMIN)
        user.role = UserRole.Role.SYSTEM_ADMIN
        return user

    def __getattr__(self, name):
        return getattr(get_user_model()._default_manager, name)


class User:
    """Compatibility facade for creating users with an HMS role."""

    Role = UserRole.Role
    objects = _RoleAwareUserManager()


def set_user_role(user, role):
    if role not in UserRole.Role.values:
        raise ValueError(f"Unknown user role: {role}")
    UserRole.objects.update_or_create(user=user, defaults={"role": role})


def get_user_role(user):
    if not user.is_authenticated:
        return None

    role_profile = getattr(user, "role_profile", None)
    if role_profile is not None:
        return role_profile.role

    return (
        UserRole.Role.WARDEN
        if user.is_staff
        else UserRole.Role.STUDENT
    )


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
    department = models.CharField(max_length=100, blank=True)
    year_of_study = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
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
    description = models.TextField(blank=True)

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
    room_number = models.CharField(max_length=20, blank=True, default="")
    room_code = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
    )
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["block__hostel__name", "block__name", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["block", "number"],
                name="unique_room_per_block",
            ),
            models.UniqueConstraint(
                fields=["block", "room_number"],
                name="unique_room_number_per_block",
            ),
            models.CheckConstraint(
                condition=Q(capacity__gte=1),
                name="room_capacity_at_least_one",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                "number",
                "room_number",
            ).first()
        else:
            previous = None

        if previous:
            number_changed = self.number != previous["number"]
            room_number_changed = self.room_number != previous["room_number"]
            if number_changed and not room_number_changed:
                self.room_number = self.number
            elif room_number_changed and not number_changed:
                self.number = self.room_number
            elif self.number != self.room_number:
                raise ValueError("Room number fields must match.")
        elif self.number and not self.room_number:
            self.room_number = self.number
        elif self.room_number and not self.number:
            self.number = self.room_number
        elif self.number != self.room_number:
            raise ValueError("Room number fields must match.")

        update_fields = kwargs.get("update_fields")
        if update_fields is not None and (
            "number" in update_fields or "room_number" in update_fields
        ):
            kwargs["update_fields"] = set(update_fields) | {
                "number",
                "room_number",
            }

        super().save(*args, **kwargs)

    @property
    def occupied_count(self):
        return self.allocations.filter(is_active=True).count()

    @property
    def available_spaces(self):
        return max(self.capacity - self.occupied_count, 0)

    def __str__(self):
        return f"{self.block} / {self.room_number}"


class Allocation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

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
    allocation_date = models.DateField(default=timezone.localdate)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    check_in_date = models.DateField(null=True, blank=True)
    check_out_date = models.DateField(null=True, blank=True)
    active_student_guard = models.OneToOneField(
        Student,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        ordering = ["room", "student__student_id"]
        indexes = [
            models.Index(
                fields=["room", "status"],
                name="allocation_room_status_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(is_active=True),
                name="one_active_allocation_per_student",
            ),
        ]

    def save(self, *args, **kwargs):
        previous = None
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                "status",
                "is_active",
            ).first()

        if previous:
            status_changed = self.status != previous["status"]
            active_changed = self.is_active != previous["is_active"]
            if status_changed and not active_changed:
                self.is_active = self.status == self.Status.ACTIVE
            elif active_changed and not status_changed:
                self.status = (
                    self.Status.ACTIVE
                    if self.is_active
                    else self.Status.COMPLETED
                )
            else:
                self.is_active = self.status == self.Status.ACTIVE
        elif self.status == self.Status.ACTIVE and not self.is_active:
            self.status = self.Status.COMPLETED
        else:
            self.is_active = self.status == self.Status.ACTIVE

        self.active_student_guard = (
            self.student if self.status == self.Status.ACTIVE else None
        )

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {
                "status",
                "is_active",
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
    decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfer_decisions",
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.decision_by and not self.reviewed_by:
            self.reviewed_by = self.decision_by
        elif self.reviewed_by and not self.decision_by:
            self.decision_by = self.reviewed_by

        if self.decided_at and not self.reviewed_at:
            self.reviewed_at = self.decided_at
        elif self.reviewed_at and not self.decided_at:
            self.decided_at = self.reviewed_at

        update_fields = kwargs.get("update_fields")
        if update_fields is not None and (
            {"decision_by", "reviewed_by", "decided_at", "reviewed_at"}
            & set(update_fields)
        ):
            kwargs["update_fields"] = set(update_fields) | {
                "decision_by",
                "reviewed_by",
                "decided_at",
                "reviewed_at",
            }

        super().save(*args, **kwargs)


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


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100, blank=True)
    entity_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    entity_id = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.actor and not self.user:
            self.user = self.actor
        elif self.user and not self.actor:
            self.actor = self.user

        if self.model_name and not self.entity_type:
            self.entity_type = self.model_name
        elif self.entity_type and not self.model_name:
            self.model_name = self.entity_type

        if self.object_id and not self.entity_id:
            self.entity_id = self.object_id
        elif self.entity_id and not self.object_id:
            self.object_id = self.entity_id

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {
                "actor",
                "user",
                "model_name",
                "entity_type",
                "object_id",
                "entity_id",
            }

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.action} - {self.created_at}"

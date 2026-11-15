from django.contrib import admin

from .forms import AllocationForm
from .models import (
    Allocation,
    AuditLog,
    Block,
    Complaint,
    Hostel,
    Room,
    Student,
    TransferRequest,
    User,
    UserRole,
    get_user_role,
)
from .services import record_audit


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    form = AllocationForm
    list_display = ("student", "room", "status", "allocation_date")
    readonly_fields = ("allocated_at", "checked_out_at")

    def save_model(self, request, obj, form, change):
        previous = None
        if change:
            previous = Allocation.objects.get(pk=obj.pk)
        super().save_model(request, obj, form, change)

        if previous is None:
            action = "allocated"
            details = {"room": str(obj.room)}
        else:
            action = "updated"
            if previous.status != obj.status:
                if obj.status == Allocation.Status.ACTIVE:
                    action = "checked_in"
                elif obj.status == Allocation.Status.COMPLETED:
                    action = "checked_out"
                elif obj.status == Allocation.Status.CANCELLED:
                    action = "cancelled"
            details = {
                "from_room": str(previous.room),
                "to_room": str(obj.room),
                "old_status": previous.status,
                "new_status": obj.status,
            }
        record_audit(action, obj, request.user, details)

    def delete_model(self, request, obj):
        record_audit("deleted", obj, request.user, {"room": str(obj.room)})
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset.select_related("room"):
            record_audit("deleted", obj, request.user, {"room": str(obj.room)})
        super().delete_queryset(request, queryset)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("room_code", "block", "number", "capacity")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_audit(
            "updated" if change else "created",
            obj,
            request.user,
        )

    def delete_model(self, request, obj):
        record_audit("deleted", obj, request.user)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            record_audit("deleted", obj, request.user)
        super().delete_queryset(request, queryset)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "model_name", "object_id")
    list_filter = ("action", "model_name", "created_at")
    search_fields = ("actor__username", "action", "model_name", "object_id")
    readonly_fields = (
        "actor",
        "action",
        "model_name",
        "object_id",
        "details",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_module_permission(self, request):
        return self._is_authorized_staff(request.user)

    def has_view_permission(self, request, obj=None):
        return self._is_authorized_staff(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @staticmethod
    def _is_authorized_staff(user):
        return user.is_authenticated and get_user_role(user) in {
            User.Role.WARDEN,
            User.Role.HOSTEL_ADMIN,
            User.Role.SYSTEM_ADMIN,
        }


admin.site.register([Hostel, Block, TransferRequest, Complaint])


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "student_id",
        "user",
        "department",
        "year_of_study",
    )
    search_fields = ("student_id", "user__username", "phone")
    list_filter = ("department", "year_of_study")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__username",)

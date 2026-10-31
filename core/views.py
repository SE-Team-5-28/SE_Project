from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AllocationForm,
    BlockForm,
    HostelForm,
    RoomForm,
    StudentForm,
    TransferRequestForm,
)
from .models import (
    Allocation,
    AuditLog,
    Block,
    Hostel,
    Room,
    Student,
    TransferRequest,
    User,
    get_user_role,
)
from .services import allocate_student
from .permissions import role_required


def staff_required(view_func):
    allowed_roles = {
        User.Role.WARDEN,
        User.Role.HOSTEL_ADMIN,
        User.Role.SYSTEM_ADMIN,
    }
    return user_passes_test(
        lambda user: get_user_role(user) in allowed_roles,
        login_url="login",
    )(view_func)


def audit(action, instance, request, details=None):
    AuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action=action,
        model_name=instance.__class__.__name__,
        object_id=str(instance.pk) if instance.pk else "",
        details=details or {},
    )


@login_required
def dashboard(request):
    context = {
        "student_count": Student.objects.count(),
        "hostel_count": Hostel.objects.count(),
        "room_count": Room.objects.count(),
        "pending_transfers": TransferRequest.objects.filter(
            status=TransferRequest.Status.PENDING
        ).count(),
    }
    return render(request, "core/dashboard.html", context)


@role_required(User.Role.STUDENT)
def student_dashboard(request):
    return render(
        request,
        "core/role_dashboard.html",
        {"page_title": "Student Dashboard"},
    )


@role_required(User.Role.WARDEN)
def warden_dashboard(request):
    return render(
        request,
        "core/role_dashboard.html",
        {"page_title": "Warden Dashboard"},
    )


@role_required(User.Role.HOSTEL_ADMIN, User.Role.SYSTEM_ADMIN)
def administrator_dashboard(request):
    return render(
        request,
        "core/role_dashboard.html",
        {"page_title": "Administrator Dashboard"},
    )


@login_required
@staff_required
def student_list(request):
    students = Student.objects.select_related("user").prefetch_related(
        "allocations__room__block__hostel"
    )
    return render(request, "core/student_list.html", {"students": students})


@login_required
@staff_required
def student_create(request):
    form = StudentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        student = form.save()
        audit("created", student, request)
        return redirect("student_list")

    return render(
        request,
        "core/student_form.html",
        {"form": form, "title": "Add Student"},
    )


@login_required
@staff_required
def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)
    form = StudentForm(request.POST or None, instance=student)
    if request.method == "POST" and form.is_valid():
        student = form.save()
        audit("updated", student, request)
        return redirect("student_list")

    return render(
        request,
        "core/student_form.html",
        {"form": form, "title": "Update Student"},
    )


@login_required
@staff_required
def hostel_list(request):
    hostels = Hostel.objects.prefetch_related("blocks__rooms__allocations")
    return render(request, "core/hostel_list.html", {"hostels": hostels})


@login_required
@staff_required
def hostel_create(request):
    form = HostelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        hostel = form.save()
        audit("created", hostel, request)
        return redirect("hostel_list")

    return render(
        request,
        "core/simple_form.html",
        {"form": form, "title": "Add Hostel"},
    )


@login_required
@staff_required
def block_create(request):
    form = BlockForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        block = form.save()
        audit("created", block, request)
        return redirect("hostel_list")

    return render(
        request,
        "core/simple_form.html",
        {"form": form, "title": "Add Block"},
    )


@login_required
@staff_required
def room_create(request):
    form = RoomForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        room = form.save()
        audit("created", room, request)
        return redirect("hostel_list")

    return render(
        request,
        "core/simple_form.html",
        {"form": form, "title": "Add Room"},
    )


@login_required
@staff_required
def allocation_list(request):
    allocations = Allocation.objects.select_related(
        "student__user",
        "room",
        "room__block",
        "room__block__hostel",
    ).order_by("-allocation_date")
    return render(
        request,
        "core/allocation_list.html",
        {"allocations": allocations},
    )


@login_required
@staff_required
@transaction.atomic
def allocation_create(request):
    form = AllocationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            allocation = allocate_student(
                student_id=form.cleaned_data["student"].pk,
                room_id=form.cleaned_data["room"].pk,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            allocation.student.hostel_name = allocation.room.block.hostel.name
            allocation.student.room_number = allocation.room.room_number
            allocation.student.save(
                update_fields=["hostel_name", "room_number", "updated_at"]
            )
            audit("allocated", allocation, request, {"room": str(allocation.room)})
            messages.success(request, "Room allocated successfully.")
            return redirect("allocation_list")

    return render(
        request,
        "core/simple_form.html",
        {"form": form, "title": "Allocate Room"},
    )


@login_required
@staff_required
@require_POST
@transaction.atomic
def check_in(request, pk):
    allocation = get_object_or_404(
        Allocation.objects.select_for_update(),
        pk=pk,
    )
    if allocation.status == Allocation.Status.ACTIVE:
        messages.warning(request, "This student is already checked in.")
        return redirect("allocation_list")

    room = get_object_or_404(
        Room.objects.select_for_update(),
        pk=allocation.room_id,
    )
    if Allocation.objects.filter(
        student=allocation.student,
        status=Allocation.Status.ACTIVE,
    ).exists():
        messages.error(
            request,
            "This student already has an active room allocation.",
        )
        return redirect("allocation_list")

    if room.available_spaces <= 0:
        messages.error(
            request,
            "This room is full. Check-in cannot be completed.",
        )
        return redirect("allocation_list")

    allocation.status = Allocation.Status.ACTIVE
    allocation.check_in_date = timezone.localdate()
    allocation.check_out_date = None
    allocation.save(
        update_fields=["status", "check_in_date", "check_out_date",
                       "active_student_guard", "is_active"]
    )
    allocation.student.hostel_name = room.block.hostel.name
    allocation.student.room_number = room.room_number
    allocation.student.save(
        update_fields=["hostel_name", "room_number", "updated_at"]
    )
    audit("checked_in", allocation, request, {"room": str(room)})
    messages.success(
        request,
        f"{allocation.student.full_name} has been checked in successfully.",
    )
    return redirect("allocation_list")


@login_required
@staff_required
@require_POST
@transaction.atomic
def check_out(request, pk):
    allocation = get_object_or_404(
        Allocation.objects.select_for_update(),
        pk=pk,
    )
    if allocation.status != Allocation.Status.ACTIVE:
        messages.warning(request, "This student has already been checked out.")
        return redirect("allocation_list")

    allocation.status = Allocation.Status.COMPLETED
    allocation.check_out_date = timezone.localdate()
    allocation.checked_out_at = timezone.now()
    allocation.save(
        update_fields=[
            "status",
            "check_out_date",
            "checked_out_at",
            "active_student_guard",
            "is_active",
        ]
    )
    allocation.student.hostel_name = ""
    allocation.student.room_number = ""
    allocation.student.save(
        update_fields=["hostel_name", "room_number", "updated_at"]
    )
    audit("checked_out", allocation, request, {"room": str(allocation.room)})
    messages.success(
        request,
        f"{allocation.student.full_name} has been checked out successfully.",
    )
    return redirect("allocation_list")


@login_required
@staff_required
def transfer_list(request):
    transfer_requests = TransferRequest.objects.select_related(
        "student__user",
        "requested_room",
    )
    return render(
        request,
        "core/transfer_list.html",
        {"transfer_requests": transfer_requests},
    )


@role_required(User.Role.STUDENT)
def transfer_create(request):
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(
            request,
            "Your account is not linked to a student profile.",
        )
        return redirect("dashboard")

    form = TransferRequestForm(request.POST or None, student=student)
    if request.method == "POST" and form.is_valid():
        transfer = form.save(commit=False)
        transfer.student = student
        transfer.save()
        audit("submitted", transfer, request)
        messages.success(
            request,
            "Your room transfer request was submitted.",
        )
        return redirect("dashboard")

    return render(
        request,
        "core/simple_form.html",
        {"form": form, "title": "Request Room Transfer"},
    )


@login_required
@staff_required
@transaction.atomic
def transfer_review(request, pk, decision):
    transfer = get_object_or_404(
        TransferRequest.objects.select_for_update().select_related(
            "student",
            "requested_room",
        ),
        pk=pk,
    )
    if (
        request.method != "POST"
        or transfer.status != TransferRequest.Status.PENDING
    ):
        return redirect("transfer_list")

    if decision == "approve":
        room = transfer.requested_room
        if room is None or room.available_spaces <= 0:
            messages.error(
                request,
                "The requested room is no longer available.",
            )
            return redirect("transfer_list")

        room = get_object_or_404(
            Room.objects.select_for_update(),
            pk=room.pk,
        )
        try:
            with transaction.atomic():
                old_allocation = Allocation.objects.filter(
                    student=transfer.student,
                    status=Allocation.Status.ACTIVE,
                ).first()
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

                new_allocation = allocate_student(
                    student_id=transfer.student_id,
                    room_id=room.pk,
                )
        except ValidationError as exc:
            messages.error(request, str(exc))
            return redirect("transfer_list")

        audit("allocated", new_allocation, request, {"room": str(room)})
        transfer.student.hostel_name = room.block.hostel.name
        transfer.student.room_number = room.room_number
        transfer.student.save(
            update_fields=["hostel_name", "room_number", "updated_at"]
        )
        transfer.status = TransferRequest.Status.APPROVED
    elif decision == "reject":
        transfer.status = TransferRequest.Status.REJECTED
    else:
        return redirect("transfer_list")

    transfer.reviewed_by = request.user
    transfer.reviewed_at = timezone.now()
    transfer.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    audit(decision, transfer, request)
    return redirect("transfer_list")

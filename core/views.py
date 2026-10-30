from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AllocationForm, BlockForm, HostelForm, RoomForm, StudentForm, TransferRequestForm
from .models import Allocation, AuditLog, Block, Hostel, Room, Student, TransferRequest


def staff_required(view_func):
    return user_passes_test(lambda user: user.is_staff, login_url="login")(view_func)


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
        "pending_transfers": TransferRequest.objects.filter(status=TransferRequest.Status.PENDING).count(),
    }
    return render(request, "core/dashboard.html", context)


@login_required
@staff_required
def student_list(request):
    students = Student.objects.prefetch_related("allocations__room__block__hostel").all()
    return render(request, "core/student_list.html", {"students": students})


@login_required
@staff_required
def student_create(request):
    form = StudentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        student = form.save()
        audit("created", student, request)
        return redirect("student_list")
    return render(request, "core/student_form.html", {"form": form, "title": "Add Student"})


@login_required
@staff_required
def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)
    form = StudentForm(request.POST or None, instance=student)
    if request.method == "POST" and form.is_valid():
        student = form.save()
        audit("updated", student, request)
        return redirect("student_list")
    return render(request, "core/student_form.html", {"form": form, "title": "Update Student"})


@login_required
@staff_required
def hostel_list(request):
    hostels = Hostel.objects.prefetch_related("blocks__rooms")
    return render(request, "core/hostel_list.html", {"hostels": hostels})


@login_required
@staff_required
def hostel_create(request):
    form = HostelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        hostel = form.save()
        audit("created", hostel, request)
        return redirect("hostel_list")
    return render(request, "core/simple_form.html", {"form": form, "title": "Add Hostel"})


@login_required
@staff_required
def block_create(request):
    form = BlockForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        block = form.save()
        audit("created", block, request)
        return redirect("hostel_list")
    return render(request, "core/simple_form.html", {"form": form, "title": "Add Block"})


@login_required
@staff_required
def room_create(request):
    form = RoomForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        room = form.save()
        audit("created", room, request)
        return redirect("hostel_list")
    return render(request, "core/simple_form.html", {"form": form, "title": "Add Room"})


@login_required
@staff_required
def allocation_list(request):
    allocations = Allocation.objects.filter(is_active=True).select_related("student", "room")
    return render(request, "core/allocation_list.html", {"allocations": allocations})


@login_required
@staff_required
@transaction.atomic
def allocation_create(request):
    form = AllocationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        allocation = form.save()
        allocation.student.hostel_name = allocation.room.block.hostel.name
        allocation.student.room_number = allocation.room.number
        allocation.student.save(update_fields=["hostel_name", "room_number", "updated_at"])
        audit("allocated", allocation, request, {"room": str(allocation.room)})
        return redirect("allocation_list")
    return render(request, "core/simple_form.html", {"form": form, "title": "Allocate Room"})


@login_required
@staff_required
def transfer_list(request):
    requests = TransferRequest.objects.select_related("student", "requested_room")
    return render(request, "core/transfer_list.html", {"transfer_requests": requests})


@login_required
def transfer_create(request):
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, "Your account is not linked to a student profile.")
        return redirect("dashboard")
    form = TransferRequestForm(request.POST or None, student=student)
    if request.method == "POST" and form.is_valid():
        transfer = form.save(commit=False)
        transfer.student = student
        transfer.save()
        audit("submitted", transfer, request)
        messages.success(request, "Your room transfer request was submitted.")
        return redirect("dashboard")
    return render(request, "core/simple_form.html", {"form": form, "title": "Request Room Transfer"})


@login_required
@staff_required
@transaction.atomic
def transfer_review(request, pk, decision):
    transfer = get_object_or_404(TransferRequest.objects.select_for_update(), pk=pk)
    if request.method != "POST" or transfer.status != TransferRequest.Status.PENDING:
        return redirect("transfer_list")
    if decision == "approve":
        if transfer.requested_room.available_spaces <= 0:
            messages.error(request, "The requested room is no longer available.")
            return redirect("transfer_list")
        old = Allocation.objects.filter(student=transfer.student, is_active=True).first()
        if old:
            old.is_active = False
            old.checked_out_at = timezone.now()
            old.save(update_fields=["is_active", "checked_out_at"])
        Allocation.objects.create(
            student=transfer.student,
            room=transfer.requested_room,
            is_active=True,
        )
        transfer.student.hostel_name = transfer.requested_room.block.hostel.name
        transfer.student.room_number = transfer.requested_room.number
        transfer.student.save(update_fields=["hostel_name", "room_number", "updated_at"])
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

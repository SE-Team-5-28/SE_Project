from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import (
    AllocationForm,
    BlockForm,
    ComplaintForm,
    ComplaintUpdateForm,
    HostelForm,
    RoomForm,
    StudentForm,
    TransferRequestForm,
)
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
    get_user_role,
)
from .permissions import role_required
from .services import allocate_student, record_audit, transfer_student


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
    return record_audit(action, instance, request.user, details)


@require_GET
def healthz(request):
    return JsonResponse({"status": "ok"})


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


def _role_dashboard_context(request):
    role = get_user_role(request.user)
    role_label = dict(User.Role.choices)[role]
    context = {
        "page_title": f"{role_label} Dashboard",
        "dashboard_metrics": [],
        "dashboard_actions": [],
    }

    if role == User.Role.STUDENT:
        try:
            student = request.user.student_profile
        except Student.DoesNotExist:
            student = None

        current_allocation = None
        if student:
            current_allocation = (
                Allocation.objects.filter(
                    student=student,
                    status=Allocation.Status.ACTIVE,
                )
                .select_related("room__block__hostel")
                .first()
            )
            pending_transfers = student.transfer_requests.filter(
                status=TransferRequest.Status.PENDING,
            ).count()
            open_complaints = student.complaints.filter(
                status__in=[
                    Complaint.Status.OPEN,
                    Complaint.Status.IN_PROGRESS,
                ],
            ).count()
        else:
            pending_transfers = 0
            open_complaints = 0
            context["profile_notice"] = (
                "Your account is not linked to a student profile. "
                "Contact your hostel warden to connect your profile."
            )

        context.update(
            {
                "dashboard_intro": (
                    "View your room details and follow your hostel requests."
                ),
                "dashboard_metrics": [
                    {
                        "label": "Current room",
                        "value": (
                            str(current_allocation.room)
                            if current_allocation
                            else "Not allocated"
                        ),
                    },
                    {
                        "label": "Pending transfer requests",
                        "value": pending_transfers,
                    },
                    {
                        "label": "Open complaints",
                        "value": open_complaints,
                    },
                ],
                "dashboard_actions": [
                    {
                        "label": "Request a room transfer",
                        "url": reverse("transfer_create"),
                        "description": "Ask to move to another available room.",
                    },
                    {
                        "label": "My transfer requests",
                        "url": reverse("my_transfer_requests"),
                        "description": "Check the status of your requests.",
                    },
                    {
                        "label": "Submit a complaint",
                        "url": reverse("complaint_create"),
                        "description": "Tell hostel staff about an issue.",
                    },
                    {
                        "label": "My complaints",
                        "url": reverse("complaint_list"),
                        "description": "Review complaint status and updates.",
                    },
                ],
            }
        )
        return context

    context.update(
        {
            "dashboard_intro": (
                "Review hostel operations and take action on student requests."
            ),
            "dashboard_metrics": [
                {
                    "label": "Students",
                    "value": Student.objects.count(),
                },
                {
                    "label": "Active allocations",
                    "value": Allocation.objects.filter(
                        status=Allocation.Status.ACTIVE,
                    ).count(),
                },
                {
                    "label": "Pending transfer requests",
                    "value": TransferRequest.objects.filter(
                        status=TransferRequest.Status.PENDING,
                    ).count(),
                },
                {
                    "label": "Unresolved complaints",
                    "value": Complaint.objects.filter(
                        status__in=[
                            Complaint.Status.OPEN,
                            Complaint.Status.IN_PROGRESS,
                        ],
                    ).count(),
                },
            ],
            "dashboard_actions": [
                {
                    "label": "Student records",
                    "url": reverse("student_list"),
                    "description": "View and update student records.",
                },
                {
                    "label": "Hostels and rooms",
                    "url": reverse("hostel_list"),
                    "description": "Review hostel, block, and room details.",
                },
                {
                    "label": "Allocations",
                    "url": reverse("allocation_list"),
                    "description": "Review student room allocations.",
                },
                {
                    "label": "Pending requests",
                    "url": reverse("pending_requests"),
                    "description": "Review transfers and unresolved complaints.",
                },
                {
                    "label": "Occupancy report",
                    "url": reverse("occupancy_report"),
                    "description": "Review capacity, occupancy, and vacancies.",
                },
                {
                    "label": "Audit log",
                    "url": reverse("audit_log_list"),
                    "description": "Review recorded administrative actions.",
                },
            ],
        }
    )
    return context


@role_required(User.Role.STUDENT)
def student_dashboard(request):
    return render(
        request,
        "core/role_dashboard.html",
        _role_dashboard_context(request),
    )


@role_required(User.Role.WARDEN)
def warden_dashboard(request):
    return render(
        request,
        "core/role_dashboard.html",
        _role_dashboard_context(request),
    )


@role_required(User.Role.HOSTEL_ADMIN, User.Role.SYSTEM_ADMIN)
def administrator_dashboard(request):
    return render(
        request,
        "core/role_dashboard.html",
        _role_dashboard_context(request),
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
def hostel_update(request, pk):
    hostel = get_object_or_404(Hostel, pk=pk)
    form = HostelForm(request.POST or None, instance=hostel)
    if request.method == "POST" and form.is_valid():
        hostel = form.save()
        audit("updated", hostel, request)
        return redirect("hostel_list")

    return render(
        request,
        "core/simple_form.html",
        {"form": form, "title": "Update Hostel"},
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
def block_update(request, pk):
    block = get_object_or_404(Block, pk=pk)
    form = BlockForm(request.POST or None, instance=block)
    if request.method == "POST" and form.is_valid():
        block = form.save()
        audit("updated", block, request)
        return redirect("hostel_list")

    return render(
        request,
        "core/simple_form.html",
        {"form": form, "title": "Update Block"},
    )


@login_required
@staff_required
@transaction.atomic
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
@transaction.atomic
def room_update(request, pk):
    room = get_object_or_404(
        Room.objects.select_for_update(),
        pk=pk,
    )
    form = RoomForm(request.POST or None, instance=room)
    if request.method == "POST" and form.is_valid():
        room = form.save()
        audit("updated", room, request)
        return redirect("hostel_list")

    return render(
        request,
        "core/simple_form.html",
        {"form": form, "title": "Update Room"},
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


@role_required(
    User.Role.WARDEN,
    User.Role.HOSTEL_ADMIN,
    User.Role.SYSTEM_ADMIN,
)
@require_http_methods(["GET"])
def audit_log_list(request):
    logs = AuditLog.objects.select_related("actor")
    page = Paginator(logs, 50).get_page(request.GET.get("page"))
    return render(request, "core/audit_log_list.html", {"page": page})


@role_required(
    User.Role.WARDEN,
    User.Role.HOSTEL_ADMIN,
    User.Role.SYSTEM_ADMIN,
)
def occupancy_report(request):
    hostels = list(Hostel.objects.all())
    summaries = {
        hostel.pk: {
            "hostel": hostel,
            "capacity": 0,
            "occupied": 0,
            "vacancies": 0,
        }
        for hostel in hostels
    }

    room_summaries = Room.objects.values(
        "block__hostel_id",
        "pk",
        "capacity",
    ).annotate(
        occupied=Count(
            "allocations",
            filter=Q(allocations__status=Allocation.Status.ACTIVE),
        ),
    )

    for room in room_summaries:
        summary = summaries[room["block__hostel_id"]]
        capacity = room["capacity"]
        occupied = room["occupied"]
        summary["capacity"] += capacity
        summary["occupied"] += occupied
        summary["vacancies"] += max(capacity - occupied, 0)

    totals = {
        key: sum(summary[key] for summary in summaries.values())
        for key in ("capacity", "occupied", "vacancies")
    }
    return render(
        request,
        "core/occupancy_report.html",
        {"summaries": summaries.values(), "totals": totals},
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
        f"{allocation.student.full_name} has been checked in to "
        f"Room {room.room_number} successfully.",
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
        f"{allocation.student.full_name} has been checked out from "
        f"Room {allocation.room.room_number} successfully.",
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
        return redirect("my_transfer_requests")

    return render(
        request,
        "core/simple_form.html",
        {"form": form, "title": "Request Room Transfer"},
    )


def _student_profile_or_redirect(request):
    try:
        return request.user.student_profile
    except Student.DoesNotExist:
        messages.error(
            request,
            "Your account is not linked to a student profile.",
        )
        return None


@role_required(User.Role.STUDENT)
def my_transfer_requests(request):
    student = _student_profile_or_redirect(request)
    if student is None:
        return redirect("dashboard")

    transfer_requests = student.transfer_requests.select_related(
        "requested_room",
    ).order_by("-created_at", "-pk")
    return render(
        request,
        "core/my_transfer_requests.html",
        {"transfer_requests": transfer_requests},
    )


@role_required(User.Role.STUDENT)
def complaint_create(request):
    student = _student_profile_or_redirect(request)
    if student is None:
        return redirect("dashboard")

    form = ComplaintForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        complaint = form.save(commit=False)
        complaint.student = student
        complaint.save()
        audit("submitted", complaint, request)
        messages.success(
            request,
            f"Your complaint was submitted. Reference: {complaint.reference}",
        )
        return redirect("complaint_detail", reference=complaint.reference)

    return render(
        request,
        "core/simple_form.html",
        {"form": form, "title": "Submit Hostel Complaint"},
    )


@role_required(User.Role.STUDENT)
def complaint_list(request):
    student = _student_profile_or_redirect(request)
    if student is None:
        return redirect("dashboard")

    complaints = Complaint.objects.filter(student=student).order_by(
        "-created_at"
    )
    return render(
        request,
        "core/complaint_list.html",
        {"complaints": complaints},
    )


@role_required(User.Role.STUDENT)
def complaint_detail(request, reference):
    student = _student_profile_or_redirect(request)
    if student is None:
        return redirect("dashboard")

    complaint = get_object_or_404(
        Complaint.objects.filter(student=student),
        reference=reference,
    )
    return render(
        request,
        "core/complaint_detail.html",
        {"complaint": complaint},
    )


@role_required(
    User.Role.WARDEN,
    User.Role.HOSTEL_ADMIN,
    User.Role.SYSTEM_ADMIN,
)
@require_http_methods(["GET", "POST"])
def complaint_update(request, reference):
    complaint = get_object_or_404(Complaint, reference=reference)
    form = ComplaintUpdateForm(
        request.POST or None,
        instance=complaint,
    )
    if request.method == "POST" and form.is_valid():
        complaint = form.save()
        audit("updated", complaint, request, {"status": complaint.status})
        messages.success(request, "Complaint updated.")
        return redirect("pending_requests")

    return render(
        request,
        "core/simple_form.html",
        {"form": form, "title": "Update Complaint"},
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
        if transfer.requested_room_id is None:
            messages.error(
                request,
                "The requested room is no longer available.",
            )
            return redirect("transfer_list")

        old_allocation = (
            Allocation.objects.select_for_update()
            .filter(
                student=transfer.student,
                status=Allocation.Status.ACTIVE,
            )
            .select_related("room")
            .first()
        )
        try:
            new_allocation = transfer_student(
                student_id=transfer.student_id,
                room_id=transfer.requested_room_id,
            )
        except ValidationError as exc:
            messages.error(request, str(exc))
            return redirect("transfer_list")

        room = new_allocation.room
        if old_allocation:
            audit(
                "transferred_out",
                old_allocation,
                request,
                {
                    "from_room": str(old_allocation.room),
                    "to_room": str(room),
                    "new_allocation_id": str(new_allocation.pk),
                },
            )
            audit(
                "transferred_in",
                new_allocation,
                request,
                {
                    "from_room": str(old_allocation.room),
                    "to_room": str(room),
                    "previous_allocation_id": str(old_allocation.pk),
                },
            )
        else:
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


@login_required
@staff_required
def pending_requests_dashboard(request):
    """Show transfer requests and complaints for hostel staff."""
    transfer_status = request.GET.get("transfer_status", TransferRequest.Status.PENDING)
    valid_transfer_statuses = {value for value, _label in TransferRequest.Status.choices}
    if transfer_status not in valid_transfer_statuses:
        transfer_status = TransferRequest.Status.PENDING

    transfer_requests = (
        TransferRequest.objects.select_related("student", "requested_room")
        .filter(status=transfer_status)
        .order_by("-created_at")
    )

    complaint_status = request.GET.get("complaint_status", "UNRESOLVED")
    valid_complaint_statuses = {value for value, _label in Complaint.Status.choices}
    if complaint_status == "UNRESOLVED":
        complaints = Complaint.objects.filter(
            status__in=[Complaint.Status.OPEN, Complaint.Status.IN_PROGRESS]
        )
    elif complaint_status in valid_complaint_statuses:
        complaints = Complaint.objects.filter(status=complaint_status)
    else:
        complaint_status = "UNRESOLVED"
        complaints = Complaint.objects.filter(
            status__in=[Complaint.Status.OPEN, Complaint.Status.IN_PROGRESS]
        )

    complaints = complaints.select_related("student").order_by("-created_at")

    context = {
        "transfer_requests": transfer_requests,
        "complaints": complaints,
        "transfer_status": transfer_status,
        "complaint_status": complaint_status,
        "pending_transfer_count": TransferRequest.objects.filter(
            status=TransferRequest.Status.PENDING
        ).count(),
        "unresolved_complaint_count": Complaint.objects.filter(
            status__in=[Complaint.Status.OPEN, Complaint.Status.IN_PROGRESS]
        ).count(),
    }
    return render(request, "core/pending_requests.html", context)

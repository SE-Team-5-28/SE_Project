from django.test import TestCase
from django.urls import reverse

from core.models import (
    Block,
    Complaint,
    Hostel,
    Room,
    Student,
    TransferRequest,
    User,
)


class RoleBasedAccessTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username="test_student",
            password="TestPassword123!",
            role=User.Role.STUDENT,
        )

        self.warden = User.objects.create_user(
            username="test_warden",
            password="TestPassword123!",
            role=User.Role.WARDEN,
        )

        self.hostel_admin = User.objects.create_user(
            username="test_hostel_admin",
            password="TestPassword123!",
            role=User.Role.HOSTEL_ADMIN,
        )

        self.system_admin = User.objects.create_user(
            username="test_system_admin",
            password="TestPassword123!",
            role=User.Role.SYSTEM_ADMIN,
        )

    def test_student_can_access_student_dashboard(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("student_dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_student_cannot_access_warden_dashboard(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("warden_dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_student_cannot_access_administrator_dashboard(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("administrator_dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_warden_can_access_warden_dashboard(self):
        self.client.force_login(self.warden)

        response = self.client.get(reverse("warden_dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_warden_cannot_access_student_dashboard(self):
        self.client.force_login(self.warden)

        response = self.client.get(reverse("student_dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_warden_cannot_access_administrator_dashboard(self):
        self.client.force_login(self.warden)

        response = self.client.get(reverse("administrator_dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_hostel_admin_can_access_administrator_dashboard(self):
        self.client.force_login(self.hostel_admin)

        response = self.client.get(reverse("administrator_dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_system_admin_can_access_administrator_dashboard(self):
        self.client.force_login(self.system_admin)

        response = self.client.get(reverse("administrator_dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_administrator_cannot_access_student_dashboard(self):
        self.client.force_login(self.hostel_admin)

        response = self.client.get(reverse("student_dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_administrator_cannot_access_warden_dashboard(self):
        self.client.force_login(self.system_admin)

        response = self.client.get(reverse("warden_dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_staff_roles_can_access_occupancy_report(self):
        for user in (self.warden, self.hostel_admin, self.system_admin):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse("occupancy_report"))
                self.assertEqual(response.status_code, 200)

    def test_staff_roles_can_list_pending_transfer_requests(self):
        hostel = Hostel.objects.create(name="Transfer Access Hostel")
        block = Block.objects.create(hostel=hostel, name="A")
        room = Room.objects.create(block=block, number="101", capacity=1)
        student = Student.objects.create(
            user=self.student,
            student_id="TRANSFER-ACCESS-001",
        )
        transfer = TransferRequest.objects.create(
            student=student,
            requested_room=room,
            reason="Transfer access test",
        )

        for user in (self.warden, self.hostel_admin, self.system_admin):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse("transfer_list"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, str(transfer.pk))
                self.assertContains(response, "Pending")

    def test_student_cannot_review_transfer_with_direct_posts(self):
        hostel = Hostel.objects.create(name="Transfer Access Hostel")
        block = Block.objects.create(hostel=hostel, name="A")
        room = Room.objects.create(block=block, number="101", capacity=1)
        student = Student.objects.create(
            user=self.student,
            student_id="TRANSFER-ACCESS-001",
        )
        transfer = TransferRequest.objects.create(
            student=student,
            requested_room=room,
            reason="Transfer access test",
        )
        self.client.force_login(self.student)

        for decision in ("approve", "reject"):
            with self.subTest(decision=decision):
                response = self.client.post(
                    reverse(
                        "transfer_review",
                        args=[transfer.pk, decision],
                    )
                )
                self.assertEqual(response.status_code, 302)

        transfer.refresh_from_db()
        self.assertEqual(transfer.status, TransferRequest.Status.PENDING)
        self.assertIsNone(transfer.reviewed_by)
        self.assertIsNone(transfer.reviewed_at)
        self.assertFalse(
            student.allocations.filter(status="ACTIVE").exists()
        )

    def test_student_cannot_access_occupancy_report(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("occupancy_report"))

        self.assertEqual(response.status_code, 403)

    def test_student_cannot_access_hostel_record_management(self):
        hostel = Hostel.objects.create(name="Access Control Hostel")
        block = Block.objects.create(hostel=hostel, name="A")
        room = Room.objects.create(
            block=block,
            number="101",
            room_code="ACCESS-101",
            capacity=2,
        )
        self.client.force_login(self.student)

        for route, record in (
            ("hostel_update", hostel),
            ("block_update", block),
            ("room_update", room),
        ):
            with self.subTest(route=route):
                response = self.client.get(
                    reverse(route, args=[record.pk])
                )
                self.assertEqual(response.status_code, 302)

        for route in ("hostel_list", "hostel_create", "block_create", "room_create"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 302)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("student_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_dashboard_displays_student_navigation(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("student_dashboard"))
        self.assertNotContains(response, reverse("warden_dashboard"))

    def test_dashboard_displays_warden_navigation(self):
        self.client.force_login(self.warden)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("warden_dashboard"))
        self.assertNotContains(response, reverse("student_dashboard"))

    def test_dashboard_displays_administrator_navigation(self):
        self.client.force_login(self.hostel_admin)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("administrator_dashboard"))
        self.assertNotContains(response, reverse("student_dashboard"))
        self.assertNotContains(response, reverse("warden_dashboard"))

    def test_dashboard_displays_current_base_counts(self):
        hostel = Hostel.objects.create(name="Dashboard Hostel")
        block = Block.objects.create(hostel=hostel, name="A")
        room = Room.objects.create(block=block, number="101", capacity=1)
        student = Student.objects.create(
            user=self.student,
            student_id="DASH-STU-001",
            full_name="Dashboard Student",
            hostel_name=hostel.name,
            room_number=room.number,
        )
        TransferRequest.objects.create(
            student=student,
            requested_room=room,
            reason="Dashboard count test",
        )

        self.client.force_login(self.hostel_admin)
        response = self.client.get(reverse("dashboard"))

        self.assertContains(
            response,
            "<strong>1</strong><span>Students</span>",
            html=True,
        )
        self.assertContains(
            response,
            "<strong>1</strong><span>Hostels</span>",
            html=True,
        )
        self.assertContains(
            response,
            "<strong>1</strong><span>Rooms</span>",
            html=True,
        )
        self.assertContains(
            response,
            "<strong>1</strong><span>Pending transfers</span>",
            html=True,
        )

    def test_student_dashboard_shows_workflows_and_personal_counts(self):
        student = Student.objects.create(
            user=self.student,
            student_id="DASH-STU-002",
            full_name="Dashboard Student",
        )
        TransferRequest.objects.create(
            student=student,
            reason="Need a quieter room",
        )
        Complaint.objects.create(
            student=student,
            category="Maintenance",
            description="The desk lamp is not working.",
        )
        self.client.force_login(self.student)

        response = self.client.get(reverse("student_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student Dashboard")
        self.assertContains(response, "Current room")
        self.assertContains(response, "Not allocated")
        self.assertContains(
            response,
            "<span>Pending transfer requests</span><strong>1</strong>",
            html=True,
        )
        self.assertContains(
            response,
            "<span>Open complaints</span><strong>1</strong>",
            html=True,
        )
        self.assertContains(response, "Request a room transfer")
        self.assertContains(response, reverse("my_transfer_requests"))
        self.assertContains(response, reverse("complaint_create"))
        self.assertContains(response, reverse("complaint_list"))
        self.assertNotContains(response, reverse("student_list"))

    def test_warden_dashboard_shows_operational_content_and_navigation(self):
        self.client.force_login(self.warden)

        response = self.client.get(reverse("warden_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Warden Dashboard")
        self.assertContains(response, "Active allocations")
        self.assertContains(response, reverse("student_list"))
        self.assertContains(response, reverse("hostel_list"))
        self.assertContains(response, reverse("allocation_list"))
        self.assertContains(response, reverse("pending_requests"))
        self.assertContains(response, reverse("occupancy_report"))
        self.assertContains(response, reverse("audit_log_list"))

    def test_system_administrator_dashboard_identifies_role_and_actions(self):
        self.client.force_login(self.system_admin)

        response = self.client.get(reverse("administrator_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "System Administrator Dashboard")
        self.assertContains(response, "Your role is System Administrator")
        self.assertContains(response, reverse("student_list"))
        self.assertContains(response, reverse("audit_log_list"))

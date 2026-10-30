from django.test import TestCase
from django.urls import reverse

from core.models import (
    Block,
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
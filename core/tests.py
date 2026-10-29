
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from .models import Student


class StudentRecordTests(TestCase):

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="admin",
            password="testpassword123",
            is_staff=True
        )

        self.normal_user = User.objects.create_user(
            username="student",
            password="testpassword123"
        )

        self.student = Student.objects.create(
            student_id="PES001",
            full_name="Test Student",
            email="test@example.com",
            phone="9876543210",
            hostel_name="Hostel A",
            room_number="101"
        )

    def test_staff_can_view_student_records(self):
        self.client.login(username="admin", password="testpassword123")

        response = self.client.get(reverse("student_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PES001")
        self.assertContains(response, "Test Student")

    def test_non_staff_cannot_view_student_records(self):
        self.client.login(username="student", password="testpassword123")

        response = self.client.get(reverse("student_list"))

        self.assertEqual(response.status_code, 302)

    def test_anonymous_user_cannot_view_student_records(self):
        response = self.client.get(reverse("student_list"))

        self.assertEqual(response.status_code, 302)

    def test_staff_can_create_student(self):
        self.client.login(username="admin", password="testpassword123")

        response = self.client.post(
            reverse("student_create"),
            {
                "student_id": "PES002",
                "full_name": "New Student",
                "email": "new@example.com",
                "phone": "9876543211",
                "hostel_name": "Hostel B",
                "room_number": "202"
            }
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Student.objects.filter(student_id="PES002").exists()
        )

    def test_duplicate_student_id_is_rejected(self):
        self.client.login(username="admin", password="testpassword123")

        response = self.client.post(
            reverse("student_create"),
            {
                "student_id": "PES001",
                "full_name": "Duplicate Student",
                "email": "duplicate@example.com",
                "phone": "9876543212",
                "hostel_name": "Hostel C",
                "room_number": "303"
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Student.objects.count(), 1)
        self.assertFalse(
            Student.objects.filter(full_name="Duplicate Student").exists()
        )

    def test_staff_can_update_student(self):
        self.client.login(username="admin", password="testpassword123")

        response = self.client.post(
            reverse("student_update", args=[self.student.pk]),
            {
                "student_id": "PES001",
                "full_name": "Updated Student",
                "email": "updated@example.com",
                "phone": "9876543210",
                "hostel_name": "Hostel A",
                "room_number": "105"
            }
        )

        self.assertEqual(response.status_code, 302)

        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, "Updated Student")

    def test_student_record_can_be_retrieved(self):
        self.client.login(username="admin", password="testpassword123")

        response = self.client.get(reverse("student_list"))

        self.assertContains(response, self.student.student_id)
        self.assertContains(response, self.student.full_name)


from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from .models import (
    Allocation,
    AuditLog,
    Block,
    Hostel,
    Room,
    Student,
    TransferRequest,
)


class StudentRecordTests(TestCase):

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="admin",
            password="testpassword123",
            is_staff=True,
        )

        self.normal_user = User.objects.create_user(
            username="student",
            password="testpassword123",
        )

        self.student = Student.objects.create(
            student_id="PES001",
            full_name="Test Student",
            email="test@example.com",
            phone="9876543210",
            hostel_name="Hostel A",
            room_number="101",
        )

    def test_staff_can_view_student_records(self):
        self.client.login(
            username="admin",
            password="testpassword123",
        )

        response = self.client.get(reverse("student_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PES001")
        self.assertContains(response, "Test Student")

    def test_non_staff_cannot_view_student_records(self):
        self.client.login(
            username="student",
            password="testpassword123",
        )

        response = self.client.get(reverse("student_list"))

        self.assertEqual(response.status_code, 302)

    def test_anonymous_user_cannot_view_student_records(self):
        response = self.client.get(reverse("student_list"))

        self.assertEqual(response.status_code, 302)

    def test_staff_can_create_student(self):
        self.client.login(
            username="admin",
            password="testpassword123",
        )

        response = self.client.post(
            reverse("student_create"),
            {
                "student_id": "PES002",
                "full_name": "New Student",
                "email": "new@example.com",
                "phone": "9876543211",
                "hostel_name": "Hostel B",
                "room_number": "202",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Student.objects.filter(student_id="PES002").exists()
        )

    def test_duplicate_student_id_is_rejected(self):
        self.client.login(
            username="admin",
            password="testpassword123",
        )

        response = self.client.post(
            reverse("student_create"),
            {
                "student_id": "PES001",
                "full_name": "Duplicate Student",
                "email": "duplicate@example.com",
                "phone": "9876543212",
                "hostel_name": "Hostel C",
                "room_number": "303",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Student.objects.count(), 1)
        self.assertFalse(
            Student.objects.filter(
                full_name="Duplicate Student"
            ).exists()
        )

    def test_staff_can_update_student(self):
        self.client.login(
            username="admin",
            password="testpassword123",
        )

        response = self.client.post(
            reverse(
                "student_update",
                args=[self.student.pk],
            ),
            {
                "student_id": "PES001",
                "full_name": "Updated Student",
                "email": "updated@example.com",
                "phone": "9876543210",
                "hostel_name": "Hostel A",
                "room_number": "105",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.student.refresh_from_db()
        self.assertEqual(
            self.student.full_name,
            "Updated Student",
        )

    def test_student_record_can_be_retrieved(self):
        self.client.login(
            username="admin",
            password="testpassword123",
        )

        response = self.client.get(reverse("student_list"))

        self.assertContains(response, self.student.student_id)
        self.assertContains(response, self.student.full_name)

    def test_passwords_are_stored_using_a_hash(self):
        user = User.objects.get(username="admin")

        self.assertNotEqual(
            user.password,
            "testpassword123",
        )
        self.assertTrue(
            user.check_password("testpassword123")
        )


class HostelOperationsTests(TestCase):

    def setUp(self):
        self.staff = User.objects.create_user(
            "warden",
            password="testpassword123",
            is_staff=True,
        )

        self.student_user = User.objects.create_user(
            "linked",
            password="testpassword123",
        )

        self.student = Student.objects.create(
            user=self.student_user,
            student_id="PES100",
            full_name="Linked Student",
            hostel_name="",
            room_number="",
        )

        self.hostel = Hostel.objects.create(
            name="North Hostel",
        )

        self.block = Block.objects.create(
            hostel=self.hostel,
            name="A",
        )

        self.room = Room.objects.create(
            block=self.block,
            number="101",
            capacity=1,
        )

    def test_staff_can_allocate_available_room_and_audit_action(self):
        self.client.login(
            username="warden",
            password="testpassword123",
        )

        response = self.client.post(
            reverse("allocation_create"),
            {
                "student": self.student.pk,
                "room": self.room.pk,
            },
        )

        self.assertRedirects(
            response,
            reverse("allocation_list"),
        )

        self.assertTrue(
            Allocation.objects.filter(
                student=self.student,
                is_active=True,
            ).exists()
        )

        self.assertTrue(
            AuditLog.objects.filter(
                action="allocated",
            ).exists()
        )

    def test_full_room_cannot_receive_second_allocation(self):
        other = Student.objects.create(
            student_id="PES101",
            full_name="Other",
            hostel_name="",
            room_number="",
        )

        Allocation.objects.create(
            student=self.student,
            room=self.room,
        )

        self.client.login(
            username="warden",
            password="testpassword123",
        )

        response = self.client.post(
            reverse("allocation_create"),
            {
                "student": other.pk,
                "room": self.room.pk,
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            Allocation.objects.filter(
                student=other,
            ).exists()
        )

    def test_student_can_submit_and_staff_can_approve_transfer(self):
        destination = Room.objects.create(
            block=self.block,
            number="102",
            capacity=1,
        )

        Allocation.objects.create(
            student=self.student,
            room=self.room,
        )

        self.client.login(
            username="linked",
            password="testpassword123",
        )

        response = self.client.post(
            reverse("transfer_create"),
            {
                "requested_room": destination.pk,
                "reason": "Accessibility",
            },
        )

        self.assertRedirects(
            response,
            reverse("dashboard"),
        )

        transfer = TransferRequest.objects.get(
            student=self.student,
        )

        self.client.login(
            username="warden",
            password="testpassword123",
        )

        response = self.client.post(
            reverse(
                "transfer_review",
                args=[transfer.pk, "approve"],
            )
        )

        self.assertRedirects(
            response,
            reverse("transfer_list"),
        )

        transfer.refresh_from_db()

        self.assertEqual(
            transfer.status,
            TransferRequest.Status.APPROVED,
        )

        self.assertEqual(
            self.student.allocations.filter(
                is_active=True
            ).get().room,
            destination,
        )


class StudentCheckInOutTests(TestCase):

    def setUp(self):
        self.warden = User.objects.create_user(
            username="warden_test",
            password="testpassword123",
            is_staff=True,
        )

        self.normal_user = User.objects.create_user(
            username="student_test",
            password="testpassword123",
        )

        self.hostel = Hostel.objects.create(
            name="Check-in Hostel",
        )

        self.block = Block.objects.create(
            hostel=self.hostel,
            name="A",
        )

        self.room = Room.objects.create(
            block=self.block,
            number="101",
            capacity=2,
        )

        self.student = Student.objects.create(
            student_id="PES200",
            full_name="Check In Student",
            email="checkin@example.com",
            phone="9876543210",
            hostel_name="Check-in Hostel",
            room_number="101",
        )

        self.allocation = Allocation.objects.create(
            student=self.student,
            room=self.room,
            is_active=True,
        )

    def test_check_out_updates_stay_status_and_occupancy(self):
        self.client.login(
            username="warden_test",
            password="testpassword123",
        )

        response = self.client.post(
            reverse(
                "check_out",
                args=[self.allocation.pk],
            )
        )

        self.assertRedirects(
            response,
            reverse("allocation_list"),
        )

        self.allocation.refresh_from_db()

        self.assertFalse(self.allocation.is_active)
        self.assertIsNotNone(self.allocation.checked_out_at)
        self.assertEqual(self.room.occupied_count, 0)

        self.student.refresh_from_db()

        self.assertEqual(self.student.hostel_name, "")
        self.assertEqual(self.student.room_number, "")

        self.assertTrue(
            AuditLog.objects.filter(
                action="checked_out",
                object_id=str(self.allocation.pk),
            ).exists()
        )

    def test_check_in_reactivates_previous_allocation(self):
        self.allocation.is_active = False
        self.allocation.checked_out_at = timezone.now()
        self.allocation.save(
            update_fields=["is_active", "checked_out_at"]
        )

        self.client.login(
            username="warden_test",
            password="testpassword123",
        )

        response = self.client.post(
            reverse(
                "check_in",
                args=[self.allocation.pk],
            )
        )

        self.assertRedirects(
            response,
            reverse("allocation_list"),
        )

        self.allocation.refresh_from_db()

        self.assertTrue(self.allocation.is_active)
        self.assertIsNone(self.allocation.checked_out_at)
        self.assertEqual(self.room.available_spaces, 1)

        self.student.refresh_from_db()

        self.assertEqual(
            self.student.hostel_name,
            self.hostel.name,
        )
        self.assertEqual(
            self.student.room_number,
            self.room.number,
        )

        self.assertTrue(
            AuditLog.objects.filter(
                action="checked_in",
                object_id=str(self.allocation.pk),
            ).exists()
        )

    def test_non_staff_cannot_check_out_student(self):
        self.client.login(
            username="student_test",
            password="testpassword123",
        )

        response = self.client.post(
            reverse(
                "check_out",
                args=[self.allocation.pk],
            )
        )

        self.assertEqual(response.status_code, 302)

        self.allocation.refresh_from_db()

        self.assertTrue(self.allocation.is_active)
        self.assertIsNone(self.allocation.checked_out_at)

    def test_non_staff_cannot_check_in_student(self):
        self.allocation.is_active = False
        self.allocation.checked_out_at = timezone.now()
        self.allocation.save(
            update_fields=["is_active", "checked_out_at"]
        )

        self.client.login(
            username="student_test",
            password="testpassword123",
        )

        response = self.client.post(
            reverse(
                "check_in",
                args=[self.allocation.pk],
            )
        )

        self.assertEqual(response.status_code, 302)

        self.allocation.refresh_from_db()

        self.assertFalse(self.allocation.is_active)

    def test_duplicate_check_out_does_not_change_timestamp(self):
        self.client.login(
            username="warden_test",
            password="testpassword123",
        )

        self.client.post(
            reverse(
                "check_out",
                args=[self.allocation.pk],
            )
        )

        self.allocation.refresh_from_db()
        original_checkout_time = self.allocation.checked_out_at

        self.client.post(
            reverse(
                "check_out",
                args=[self.allocation.pk],
            )
        )

        self.allocation.refresh_from_db()

        self.assertEqual(
            self.allocation.checked_out_at,
            original_checkout_time,
        )

    def test_check_in_cannot_exceed_room_capacity(self):
        self.room.capacity = 1
        self.room.save()

        other_student = Student.objects.create(
            student_id="PES201",
            full_name="Another Student",
            hostel_name="Check-in Hostel",
            room_number="101",
        )

        Allocation.objects.create(
            student=other_student,
            room=self.room,
            is_active=True,
        )

        self.allocation.is_active = False
        self.allocation.checked_out_at = timezone.now()
        self.allocation.save(
            update_fields=["is_active", "checked_out_at"]
        )

        self.client.login(
            username="warden_test",
            password="testpassword123",
        )

        response = self.client.post(
            reverse(
                "check_in",
                args=[self.allocation.pk],
            )
        )

        self.assertRedirects(
            response,
            reverse("allocation_list"),
        )

        self.allocation.refresh_from_db()

        self.assertFalse(self.allocation.is_active)
        self.assertIsNotNone(self.allocation.checked_out_at)

    def test_anonymous_user_cannot_check_out_student(self):
        response = self.client.post(
            reverse(
                "check_out",
                args=[self.allocation.pk],
            )
        )

        self.assertEqual(response.status_code, 302)

        self.allocation.refresh_from_db()

        self.assertTrue(self.allocation.is_active)

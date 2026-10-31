from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Allocation,
    AuditLog,
    Block,
    Hostel,
    Room,
    Student,
    TransferRequest,
    UserRole,
)
from .services import allocate_student

User = get_user_model()


class StudentRecordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = User.objects.create_user(
            username="admin",
            password="testpassword123",
            is_staff=True,
        )
        cls.normal_user = User.objects.create_user(
            username="student",
            password="testpassword123",
        )
        cls.student = Student.objects.create(
            user=cls.normal_user,
            student_id="PES001",
            full_name="Test Student",
            department="Computer Science",
            year_of_study=2,
        )

    def test_staff_can_view_student_records(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("student_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.student_id)
        self.assertContains(response, self.student.full_name)

    def test_non_staff_cannot_view_student_records(self):
        self.client.force_login(self.normal_user)
        response = self.client.get(reverse("student_list"))
        self.assertEqual(response.status_code, 302)

    def test_anonymous_user_cannot_view_student_records(self):
        response = self.client.get(reverse("student_list"))
        self.assertEqual(response.status_code, 302)

    def test_staff_can_create_student(self):
        user = User.objects.create_user(
            username="new_student",
            password="testpassword123",
        )
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("student_create"),
            {
                "user": user.pk,
                "student_id": "PES002",
                "department": "Information Science",
                "year_of_study": 1,
            },
        )
        self.assertRedirects(response, reverse("student_list"))
        self.assertTrue(Student.objects.filter(student_id="PES002").exists())

    def test_duplicate_student_id_is_rejected(self):
        duplicate_user = User.objects.create_user(
            username="duplicate",
            password="testpassword123",
        )
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("student_create"),
            {
                "user": duplicate_user.pk,
                "student_id": "PES001",
                "department": "Computer Science",
                "year_of_study": 2,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Student.objects.count(), 1)

    def test_staff_can_update_student(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("student_update", args=[self.student.pk]),
            {
                "user": self.normal_user.pk,
                "student_id": "PES001",
                "department": "Mathematics",
                "year_of_study": 3,
            },
        )
        self.assertRedirects(response, reverse("student_list"))
        self.student.refresh_from_db()
        self.assertEqual(self.student.department, "Mathematics")
        self.assertEqual(self.student.year_of_study, 3)

    def test_passwords_are_stored_using_a_hash(self):
        self.assertNotEqual(self.staff_user.password, "testpassword123")
        self.assertTrue(self.staff_user.check_password("testpassword123"))


class HostelOperationsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="warden",
            password="testpassword123",
            is_staff=True,
        )
        self.student_user = User.objects.create_user(
            username="linked",
            password="testpassword123",
            first_name="Linked",
            last_name="Student",
        )
        self.student = Student.objects.create(
            user=self.student_user,
            student_id="PES100",
        )
        self.hostel = Hostel.objects.create(name="North Hostel")
        self.block = Block.objects.create(hostel=self.hostel, name="A")
        self.room = Room.objects.create(
            block=self.block,
            number="101",
            room_code="NORTH-A-101",
            capacity=1,
        )

    def test_staff_can_allocate_available_room_and_audit_action(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("allocation_create"),
            {"student": self.student.pk, "room": self.room.pk},
        )
        self.assertRedirects(response, reverse("allocation_list"))
        self.assertTrue(
            Allocation.objects.filter(
                student=self.student,
                status=Allocation.Status.ACTIVE,
            ).exists()
        )
        self.assertTrue(AuditLog.objects.filter(action="allocated").exists())

    def test_full_room_cannot_receive_second_allocation(self):
        other_user = User.objects.create_user(
            username="other",
            password="testpassword123",
        )
        other = Student.objects.create(user=other_user, student_id="PES101")
        Allocation.objects.create(student=self.student, room=self.room)

        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("allocation_create"),
            {"student": other.pk, "room": self.room.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Allocation.objects.filter(student=other).exists())

    def test_student_can_submit_and_staff_can_approve_transfer(self):
        destination = Room.objects.create(
            block=self.block,
            number="102",
            room_code="NORTH-A-102",
            capacity=1,
        )
        Allocation.objects.create(student=self.student, room=self.room)

        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse("transfer_create"),
            {"requested_room": destination.pk, "reason": "Accessibility"},
        )
        self.assertRedirects(response, reverse("dashboard"))
        transfer = TransferRequest.objects.get(student=self.student)

        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("transfer_review", args=[transfer.pk, "approve"])
        )
        self.assertRedirects(response, reverse("transfer_list"))
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, TransferRequest.Status.APPROVED)
        self.assertEqual(
            self.student.allocations.get(status=Allocation.Status.ACTIVE).room,
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
        self.hostel = Hostel.objects.create(name="Check-in Hostel")
        self.block = Block.objects.create(hostel=self.hostel, name="A")
        self.room = Room.objects.create(
            block=self.block,
            number="101",
            room_code="CHECKIN-A-101",
            capacity=2,
        )
        self.student = Student.objects.create(
            user=self.normal_user,
            student_id="PES200",
            phone="9876543210",
        )
        self.allocation = Allocation.objects.create(
            student=self.student,
            room=self.room,
        )

    def test_check_out_updates_stay_status_and_occupancy(self):
        self.client.force_login(self.warden)
        response = self.client.post(
            reverse("check_out", args=[self.allocation.pk])
        )
        self.assertRedirects(response, reverse("allocation_list"))
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.status, Allocation.Status.COMPLETED)
        self.assertIsNotNone(self.allocation.check_out_date)
        self.assertEqual(self.room.occupied_count, 0)
        self.assertTrue(
            AuditLog.objects.filter(
                action="checked_out",
                object_id=str(self.allocation.pk),
            ).exists()
        )

    def test_check_in_reactivates_previous_allocation(self):
        self.allocation.status = Allocation.Status.COMPLETED
        self.allocation.check_out_date = timezone.localdate()
        self.allocation.save()
        self.client.force_login(self.warden)
        response = self.client.post(
            reverse("check_in", args=[self.allocation.pk])
        )
        self.assertRedirects(response, reverse("allocation_list"))
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.status, Allocation.Status.ACTIVE)
        self.assertIsNone(self.allocation.check_out_date)
        self.assertEqual(self.room.available_spaces, 1)

    def test_non_staff_cannot_check_out_student(self):
        self.client.force_login(self.normal_user)
        response = self.client.post(
            reverse("check_out", args=[self.allocation.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.status, Allocation.Status.ACTIVE)

    def test_non_staff_cannot_check_in_student(self):
        self.allocation.status = Allocation.Status.COMPLETED
        self.allocation.save()
        self.client.force_login(self.normal_user)
        response = self.client.post(
            reverse("check_in", args=[self.allocation.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.status, Allocation.Status.COMPLETED)

    def test_duplicate_check_out_does_not_change_timestamp(self):
        self.client.force_login(self.warden)
        self.client.post(reverse("check_out", args=[self.allocation.pk]))
        self.allocation.refresh_from_db()
        original_checkout_date = self.allocation.check_out_date
        self.client.post(reverse("check_out", args=[self.allocation.pk]))
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.check_out_date, original_checkout_date)

    def test_check_in_cannot_exceed_room_capacity(self):
        self.room.capacity = 1
        self.room.save()
        other_user = User.objects.create_user(
            username="other_student",
            password="testpassword123",
        )
        other_student = Student.objects.create(
            user=other_user,
            student_id="PES201",
        )
        Allocation.objects.create(student=other_student, room=self.room)
        self.allocation.status = Allocation.Status.COMPLETED
        self.allocation.save()

        self.client.force_login(self.warden)
        response = self.client.post(
            reverse("check_in", args=[self.allocation.pk])
        )
        self.assertRedirects(response, reverse("allocation_list"))
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.status, Allocation.Status.COMPLETED)

    def test_anonymous_user_cannot_check_out_student(self):
        response = self.client.post(
            reverse("check_out", args=[self.allocation.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.status, Allocation.Status.ACTIVE)


class CoreModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user1 = User.objects.create_user(username="student_one")
        cls.user2 = User.objects.create_user(username="student_two")
        cls.student1 = Student.objects.create(
            user=cls.user1,
            student_id="TEST-STU-001",
            department="Computer Science",
            year_of_study=2,
        )
        cls.student2 = Student.objects.create(
            user=cls.user2,
            student_id="TEST-STU-002",
            department="Information Science",
            year_of_study=2,
        )
        cls.hostel = Hostel.objects.create(
            name="Test Hostel",
            address="Test Address",
        )
        cls.block = Block.objects.create(hostel=cls.hostel, name="Block A")
        cls.room1 = Room.objects.create(
            block=cls.block,
            number="101",
            room_code="TEST-A-101",
            capacity=2,
        )
        cls.room2 = Room.objects.create(
            block=cls.block,
            number="102",
            room_code="TEST-A-102",
            capacity=2,
        )

    def test_user_defaults_to_student_role(self):
        user = User.objects.create_user(username="default_role_user")
        role = UserRole.objects.create(user=user)
        self.assertEqual(role.role, UserRole.Role.STUDENT)

    def test_student_id_must_be_unique(self):
        user = User.objects.create_user(username="duplicate_student")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Student.objects.create(user=user, student_id="TEST-STU-001")

    def test_room_code_must_be_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Room.objects.create(
                    block=self.block,
                    number="103",
                    room_code="TEST-A-101",
                    capacity=2,
                )

    def test_room_number_must_be_unique_within_block(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Room.objects.create(
                    block=self.block,
                    number="101",
                    room_code="TEST-A-103",
                    capacity=2,
                )

    def test_room_numbers_can_repeat_in_different_blocks(self):
        other_block = Block.objects.create(hostel=self.hostel, name="Block B")
        room = Room.objects.create(
            block=other_block,
            number="101",
            room_code="TEST-B-101",
            capacity=2,
        )
        self.assertEqual(room.room_number, "101")

    def test_student_cannot_have_two_active_allocations(self):
        Allocation.objects.create(
            student=self.student1,
            room=self.room1,
            status=Allocation.Status.ACTIVE,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Allocation.objects.create(
                    student=self.student1,
                    room=self.room2,
                    status=Allocation.Status.ACTIVE,
                )

    def test_student_can_receive_new_allocation_after_completion(self):
        allocation = Allocation.objects.create(
            student=self.student1,
            room=self.room1,
        )
        allocation.status = Allocation.Status.COMPLETED
        allocation.save()
        new_allocation = Allocation.objects.create(
            student=self.student1,
            room=self.room2,
        )
        self.assertEqual(new_allocation.active_student_guard, self.student1)

    def test_room_capacity_must_be_at_least_one(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Room.objects.create(
                    block=self.block,
                    number="104",
                    room_code="TEST-A-104",
                    capacity=0,
                )


class CoreDataMigrationTests(TransactionTestCase):
    migrate_from = ("core", "0002_student_user_auditlog_hostel_block_room_allocation_and_more")
    migrate_to = ("core", "0003_complaint_userrole_and_more")

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps

        User = old_apps.get_model("auth", "User")
        Student = old_apps.get_model("core", "Student")
        Hostel = old_apps.get_model("core", "Hostel")
        Block = old_apps.get_model("core", "Block")
        Room = old_apps.get_model("core", "Room")
        Allocation = old_apps.get_model("core", "Allocation")
        TransferRequest = old_apps.get_model("core", "TransferRequest")

        self.user = User.objects.create(
            username="migrated_student",
            password="!",
        )
        self.warden = User.objects.create(
            username="migrated_warden",
            password="!",
        )
        self.student = Student.objects.create(
            user=self.user,
            student_id="MIGRATE-001",
            full_name="Migrated Student",
            email="migrated@example.com",
            phone="5550100",
            hostel_name="Old Hostel",
            room_number="101",
        )
        hostel = Hostel.objects.create(
            name="Old Hostel",
            address="Old address",
            warden=self.warden,
        )
        block = Block.objects.create(hostel=hostel, name="A")
        room = Room.objects.create(block=block, number="101", capacity=2)
        active = Allocation.objects.create(student=self.student, room=room)
        inactive = Allocation.objects.create(
            student=self.student,
            room=room,
            is_active=False,
        )
        inactive.checked_out_at = timezone.now()
        inactive.save(update_fields=["checked_out_at"])
        transfer = TransferRequest.objects.create(
            student=self.student,
            requested_room=room,
            reason="Migration fixture",
            status="approved",
            reviewed_by=self.warden,
        )

        self.active_id = active.pk
        self.inactive_id = inactive.pk
        self.transfer_id = transfer.pk
        self.room_id = room.pk
        self.user_id = self.user.pk
        self.warden_id = self.warden.pk

    def tearDown(self):
        MigrationExecutor(connection).migrate([self.migrate_to])
        super().tearDown()

    def test_existing_records_are_backfilled_by_forward_migration(self):
        MigrationExecutor(connection).migrate([self.migrate_to])
        new_apps = MigrationExecutor(connection).loader.project_state(
            [self.migrate_to]
        ).apps
        Allocation = new_apps.get_model("core", "Allocation")
        Room = new_apps.get_model("core", "Room")
        TransferRequest = new_apps.get_model("core", "TransferRequest")
        UserRole = new_apps.get_model("core", "UserRole")

        active = Allocation.objects.get(pk=self.active_id)
        inactive = Allocation.objects.get(pk=self.inactive_id)
        self.assertEqual(active.status, "ACTIVE")
        self.assertEqual(active.active_student_guard_id, self.student.pk)
        self.assertEqual(inactive.status, "COMPLETED")
        self.assertIsNone(inactive.active_student_guard_id)
        self.assertEqual(
            inactive.check_out_date,
            inactive.checked_out_at.date(),
        )
        self.assertEqual(
            Room.objects.get(pk=self.room_id).room_code,
            f"LEGACY-{self.room_id}",
        )
        self.assertEqual(
            TransferRequest.objects.get(pk=self.transfer_id).status,
            "APPROVED",
        )
        self.assertEqual(
            UserRole.objects.get(user_id=self.user_id).role,
            "STUDENT",
        )
        self.assertEqual(
            UserRole.objects.get(user_id=self.warden_id).role,
            "WARDEN",
        )


class SeedDemoCommandTests(TestCase):
    def test_seed_demo_is_repeatable_and_reports_created_data(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        call_command("seed_demo", stdout=StringIO())

        self.assertEqual(Hostel.objects.filter(name="Demo Hostel").count(), 1)
        self.assertEqual(
            Block.objects.filter(hostel__name="Demo Hostel").count(),
            2,
        )
        self.assertEqual(
            Room.objects.filter(block__hostel__name="Demo Hostel").count(),
            3,
        )
        self.assertEqual(
            Student.objects.filter(
                student_id__startswith="DEMO-STU-"
            ).count(),
            2,
        )
        self.assertEqual(
            Allocation.objects.filter(
                student__student_id="DEMO-STU-001",
                status=Allocation.Status.ACTIVE,
            ).count(),
            1,
        )
        self.assertIn("4 users, 2 students, and 1 active allocation.", output.getvalue())
class AllocationServiceTests(TestCase):
    def setUp(self):
        self.hostel = Hostel.objects.create(name="Service Hostel")
        self.block = Block.objects.create(hostel=self.hostel, name="A")
        self.room = Room.objects.create(
            block=self.block,
            number="101",
            room_code="SERVICE-101",
            capacity=1,
        )
        self.student_one = Student.objects.create(
            student_id="SERVICE001",
            full_name="Service Student One",
        )
        self.student_two = Student.objects.create(
            student_id="SERVICE002",
            full_name="Service Student Two",
        )

    def test_service_allocates_student_when_room_has_space(self):
        allocation = allocate_student(self.student_one.pk, self.room.pk)

        self.assertEqual(allocation.status, Allocation.Status.ACTIVE)
        self.assertEqual(allocation.active_student_guard_id, self.student_one.pk)
        self.assertEqual(self.room.available_spaces, 0)

    def test_service_rejects_allocation_when_room_is_full(self):
        allocate_student(self.student_one.pk, self.room.pk)

        with self.assertRaisesMessage(
            ValidationError,
            "This room is already at full capacity.",
        ):
            allocate_student(self.student_two.pk, self.room.pk)

    def test_service_rejects_second_active_allocation_for_student(self):
        allocate_student(self.student_one.pk, self.room.pk)
        other_room = Room.objects.create(
            block=self.block,
            number="102",
            room_code="SERVICE-102",
            capacity=1,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "This student already has an active allocation.",
        ):
            allocate_student(self.student_one.pk, other_room.pk)

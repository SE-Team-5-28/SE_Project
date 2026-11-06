from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Allocation,
    AuditLog,
    Block,
    Complaint,
    Hostel,
    Room,
    Student,
    TransferRequest,
    UserRole,
)
from .services import allocate_student

User = get_user_model()


class AuthenticationWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="login_student",
            password="testpassword123",
        )

    def test_user_can_log_in_with_valid_credentials(self):
        response = self.client.post(
            reverse("login"),
            {"username": "login_student", "password": "testpassword123"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(
            self.client.get(reverse("dashboard")).status_code,
            200,
        )

    def test_user_cannot_log_in_with_invalid_password(self):
        response = self.client.post(
            reverse("login"),
            {"username": "login_student", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password")
        self.assertRedirects(
            self.client.get(reverse("dashboard")),
            f"{reverse('login')}?next={reverse('dashboard')}",
        )

    def test_user_can_log_out(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        self.assertRedirects(
            self.client.get(reverse("dashboard")),
            f"{reverse('login')}?next={reverse('dashboard')}",
        )


@override_settings(
    SECURE_SSL_REDIRECT=True,
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
)
class HttpsProxySecurityTests(SimpleTestCase):
    def test_forwarded_https_request_is_not_redirected_again(self):
        response = self.client.get(
            reverse("login"),
            HTTP_HOST="localhost",
            HTTP_X_FORWARDED_PROTO="https",
        )

        self.assertEqual(response.status_code, 200)

    def test_http_request_is_redirected_to_https(self):
        response = self.client.get(
            reverse("login"),
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            f"https://localhost{reverse('login')}",
        )


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

    def test_occupancy_report_counts_active_allocations_and_vacancies(self):
        larger_room = Room.objects.create(
            block=self.block,
            number="102",
            room_code="NORTH-A-102",
            capacity=2,
        )
        empty_hostel = Hostel.objects.create(name="Empty Hostel")
        historical_user = User.objects.create_user(
            username="historical_student",
            password="testpassword123",
        )
        historical_student = Student.objects.create(
            user=historical_user,
            student_id="PES102",
        )
        Allocation.objects.create(student=self.student, room=self.room)
        Allocation.objects.create(
            student=historical_student,
            room=larger_room,
            status=Allocation.Status.COMPLETED,
        )

        self.client.force_login(self.staff)
        response = self.client.get(reverse("occupancy_report"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["totals"],
            {"capacity": 3, "occupied": 1, "vacancies": 2},
        )
        empty_summary = next(
            summary
            for summary in response.context["summaries"]
            if summary["hostel"] == empty_hostel
        )
        self.assertEqual(
            (empty_summary["capacity"], empty_summary["occupied"],
             empty_summary["vacancies"]),
            (0, 0, 0),
        )

    def test_staff_can_create_room_and_audit_action(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("room_create"),
            {
                "block": self.block.pk,
                "number": "102",
                "room_code": "NORTH-A-102",
                "capacity": 2,
            },
        )

        self.assertRedirects(response, reverse("hostel_list"))
        room = Room.objects.get(room_code="NORTH-A-102")
        self.assertEqual(room.block, self.block)
        self.assertEqual(room.capacity, 2)
        self.assertTrue(
            AuditLog.objects.filter(
                action="created",
                model_name="Room",
                object_id=str(room.pk),
            ).exists()
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

    def test_student_cannot_be_allocated_to_a_second_room(self):
        other_room = Room.objects.create(
            block=self.block,
            number="102",
            room_code="NORTH-A-102",
            capacity=1,
        )
        Allocation.objects.create(student=self.student, room=self.room)

        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("allocation_create"),
            {"student": self.student.pk, "room": other_room.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Allocation.objects.filter(
                student=self.student,
                status=Allocation.Status.ACTIVE,
            ).count(),
            1,
        )
        self.assertEqual(
            self.student.allocations.get(status=Allocation.Status.ACTIVE).room,
            self.room,
        )

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


class ComplaintSubmissionTests(TestCase):
    def setUp(self):
        self.student_user = User.objects.create_user(
            username="complaint_student",
            password="testpassword123",
        )
        self.student = Student.objects.create(
            user=self.student_user,
            student_id="CMP001",
        )
        self.other_user = User.objects.create_user(
            username="other_complaint_student",
            password="testpassword123",
        )
        self.other_student = Student.objects.create(
            user=self.other_user,
            student_id="CMP002",
        )

    def test_student_can_submit_complaint_with_unique_reference_and_open_status(self):
        self.client.force_login(self.student_user)
        response = self.client.post(
            reverse("complaint_create"),
            {
                "category": "Maintenance",
                "description": "The room fan is not working.",
            },
        )

        complaint = Complaint.objects.get(student=self.student)
        self.assertRedirects(
            response,
            reverse("complaint_detail", args=[complaint.reference]),
        )
        self.assertEqual(complaint.status, Complaint.Status.OPEN)
        self.assertIsNotNone(complaint.reference)

        second_complaint = Complaint.objects.create(
            student=self.student,
            category="Cleaning",
            description="The room needs cleaning.",
        )
        self.assertNotEqual(complaint.reference, second_complaint.reference)

    def test_student_can_list_and_retrieve_their_complaint(self):
        complaint = Complaint.objects.create(
            student=self.student,
            category="Electrical",
            description="The light needs repair.",
        )
        self.client.force_login(self.student_user)

        list_response = self.client.get(reverse("complaint_list"))
        detail_response = self.client.get(
            reverse("complaint_detail", args=[complaint.reference])
        )

        self.assertContains(list_response, str(complaint.reference))
        self.assertContains(detail_response, "The light needs repair.")
        self.assertContains(detail_response, "Open")

    def test_student_cannot_retrieve_another_students_complaint(self):
        complaint = Complaint.objects.create(
            student=self.other_student,
            category="Maintenance",
            description="Private complaint details.",
        )
        self.client.force_login(self.student_user)

        response = self.client.get(
            reverse("complaint_detail", args=[complaint.reference])
        )

        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_cannot_submit_or_list_complaints(self):
        create_response = self.client.get(reverse("complaint_create"))
        list_response = self.client.get(reverse("complaint_list"))

        self.assertRedirects(
            create_response,
            f"{reverse('login')}?next={reverse('complaint_create')}",
        )
        self.assertRedirects(
            list_response,
            f"{reverse('login')}?next={reverse('complaint_list')}",
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


from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .forms import StudentForm, RoomForm
from .models import Student, Hostel, Block, Room


User = get_user_model()


class InputValidationSecurityTests(TestCase):

    def setUp(self):
        self.staff = User.objects.create_user(
            username="security_warden",
            password="TestPassword123!",
            is_staff=True,
        )

        self.student_user = User.objects.create_user(
            username="security_student",
            password="TestPassword123!",
        )

        self.hostel = Hostel.objects.create(name="Security Hostel")
        self.block = Block.objects.create(
            hostel=self.hostel,
            name="Block A",
        )

        self.room = Room.objects.create(
            block=self.block,
            number="101",
            room_code="SECURITY-101",
            capacity=2,
        )

    def test_valid_student_input_is_accepted(self):
        form = StudentForm(data={
            "user": self.student_user.pk,
            "student_id": "PES999",
            "full_name": "Test Student",
            "email": "test@example.com",
            "phone": "9876543210",
            "hostel_name": "",
            "room_number": "",
            "department": "Computer Science",
            "year_of_study": 2,
        })

        self.assertTrue(form.is_valid(), form.errors)

    def test_sql_injection_student_id_is_rejected(self):
        form = StudentForm(data={
            "user": self.student_user.pk,
            "student_id": "' OR '1'='1",
            "full_name": "Test Student",
            "email": "test@example.com",
            "phone": "9876543210",
            "hostel_name": "",
            "room_number": "",
            "department": "Computer Science",
            "year_of_study": 2,
        })

        self.assertFalse(form.is_valid())
        self.assertIn("student_id", form.errors)

    def test_invalid_phone_number_is_rejected(self):
        form = StudentForm(data={
            "user": self.student_user.pk,
            "student_id": "PES998",
            "full_name": "Test Student",
            "email": "test@example.com",
            "phone": "phone<script>alert(1)</script>",
            "hostel_name": "",
            "room_number": "",
            "department": "Computer Science",
            "year_of_study": 2,
        })

        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

    def test_invalid_room_code_is_rejected(self):
        form = RoomForm(data={
            "block": self.block.pk,
            "number": "102",
            "room_code": "' OR 1=1 --",
            "capacity": 2,
            "description": "",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("room_code", form.errors)

    def test_oversized_transfer_reason_is_rejected(self):
        from .forms import TransferRequestForm

        form = TransferRequestForm(data={
            "requested_room": self.room.pk,
            "reason": "A" * 1001,
        })

        self.assertFalse(form.is_valid())
        self.assertIn("reason", form.errors)

    def test_injection_string_does_not_change_orm_query(self):
        Student.objects.create(
            user=self.student_user,
            student_id="PES997",
        )

        malicious_input = "' OR '1'='1"

        # Django treats the supplied value as data, not SQL.
        result = Student.objects.filter(
            student_id=malicious_input
        )

        self.assertEqual(result.count(), 0)
        self.assertEqual(Student.objects.count(), 1)

    def test_invalid_input_is_rejected_by_student_create_view(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("student_create"),
            {
                "user": self.student_user.pk,
                "student_id": "' OR '1'='1",
                "full_name": "Test Student",
                "email": "test@example.com",
                "phone": "9876543210",
                "hostel_name": "",
                "room_number": "",
                "department": "Computer Science",
                "year_of_study": 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Student.objects.filter(
                student_id="' OR '1'='1"
            ).exists()
        )


class PendingRequestsDashboardTests(TestCase):
    def setUp(self):
        self.warden = User.objects.create_user(
            username="issue17_warden",
            password="testpassword123",
            is_staff=True,
        )
        self.student = Student.objects.create(
            student_id="ISSUE17-001",
            full_name="Issue 17 Test Student",
        )
        self.hostel = Hostel.objects.create(name="Issue 17 Hostel")
        self.block = Block.objects.create(hostel=self.hostel, name="A")
        self.room = Room.objects.create(
            block=self.block,
            number="101",
            room_code="ISSUE17-101",
            capacity=2,
        )
        TransferRequest.objects.create(
            student=self.student,
            requested_room=self.room,
            reason="Request to change room",
            status=TransferRequest.Status.PENDING,
        )
        TransferRequest.objects.create(
            student=self.student,
            requested_room=self.room,
            reason="Previously approved request",
            status=TransferRequest.Status.APPROVED,
        )
        Complaint.objects.create(
            student=self.student,
            category="Maintenance",
            description="The room fan is not working.",
            status=Complaint.Status.OPEN,
        )
        Complaint.objects.create(
            student=self.student,
            category="Electrical",
            description="The light needs repair.",
            status=Complaint.Status.IN_PROGRESS,
        )
        Complaint.objects.create(
            student=self.student,
            category="Cleaning",
            description="The room was not cleaned.",
            status=Complaint.Status.RESOLVED,
        )
        self.client.force_login(self.warden)

    def test_dashboard_displays_pending_transfers(self):
        response = self.client.get(reverse("pending_requests"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Request to change room")
        self.assertNotContains(response, "Previously approved request")

    def test_dashboard_displays_unresolved_complaints(self):
        response = self.client.get(reverse("pending_requests"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The room fan is not working.")
        self.assertContains(response, "The light needs repair.")
        self.assertNotContains(response, "The room was not cleaned.")

    def test_transfer_status_filter_displays_approved_requests(self):
        response = self.client.get(
            reverse("pending_requests"), {"transfer_status": "APPROVED"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Previously approved request")
        self.assertNotContains(response, "Request to change room")

    def test_complaint_status_filter_displays_resolved_complaints(self):
        response = self.client.get(
            reverse("pending_requests"), {"complaint_status": "RESOLVED"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The room was not cleaned.")
        self.assertNotContains(response, "The room fan is not working.")

    def test_student_cannot_access_dashboard(self):
        student_user = User.objects.create_user(
            username="issue17_student", password="testpassword123"
        )
        self.client.force_login(student_user)
        response = self.client.get(reverse("pending_requests"))
        self.assertEqual(response.status_code, 302)

    def test_anonymous_user_cannot_access_dashboard(self):
        self.client.logout()
        response = self.client.get(reverse("pending_requests"))
        self.assertEqual(response.status_code, 302)

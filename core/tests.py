from django.db import IntegrityError, transaction
from django.test import TestCase

from core.models import (
    Allocation,
    Block,
    Hostel,
    Room,
    Student,
    User,
)


class CoreModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user1 = User.objects.create_user(
            username="student_one",
            password="test-password-123",
        )
        cls.user2 = User.objects.create_user(
            username="student_two",
            password="test-password-123",
        )

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
        cls.block = Block.objects.create(
            hostel=cls.hostel,
            name="Block A",
        )
        cls.room1 = Room.objects.create(
            block=cls.block,
            room_number="101",
            room_code="TEST-A-101",
            capacity=2,
        )
        cls.room2 = Room.objects.create(
            block=cls.block,
            room_number="102",
            room_code="TEST-A-102",
            capacity=2,
        )

    def test_user_defaults_to_student_role(self):
        user = User.objects.create_user(
            username="default_role_user",
            password="test-password-123",
        )
        self.assertEqual(user.role, User.Role.STUDENT)

    def test_student_id_must_be_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Student.objects.create(
                    user=User.objects.create_user(
                        username="duplicate_student",
                        password="test-password-123",
                    ),
                    student_id="TEST-STU-001",
                )

    def test_room_code_must_be_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Room.objects.create(
                    block=self.block,
                    room_number="103",
                    room_code="TEST-A-101",
                    capacity=2,
                )

    def test_room_number_must_be_unique_within_block(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Room.objects.create(
                    block=self.block,
                    room_number="101",
                    room_code="TEST-A-103",
                    capacity=2,
                )

    def test_room_numbers_can_repeat_in_different_blocks(self):
        other_block = Block.objects.create(
            hostel=self.hostel,
            name="Block B",
        )
        room = Room.objects.create(
            block=other_block,
            room_number="101",
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
            status=Allocation.Status.ACTIVE,
        )

        allocation.status = Allocation.Status.COMPLETED
        allocation.save()

        new_allocation = Allocation.objects.create(
            student=self.student1,
            room=self.room2,
            status=Allocation.Status.ACTIVE,
        )

        self.assertEqual(
            new_allocation.active_student_guard,
            self.student1,
        )

    def test_room_capacity_must_be_at_least_one(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Room.objects.create(
                    block=self.block,
                    room_number="104",
                    room_code="TEST-A-104",
                    capacity=0,
                )

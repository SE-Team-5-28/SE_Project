import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from core.models import Allocation, Block, Hostel, Room, Student, User
from core.services import allocate_student


class AllocationConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user1 = User.objects.create_user(
            username="concurrent_student_one",
            password="test-password-123",
        )
        self.user2 = User.objects.create_user(
            username="concurrent_student_two",
            password="test-password-123",
        )

        self.student1 = Student.objects.create(
            user=self.user1,
            student_id="CONCURRENT-001",
        )
        self.student2 = Student.objects.create(
            user=self.user2,
            student_id="CONCURRENT-002",
        )

        hostel = Hostel.objects.create(name="Concurrency Test Hostel")
        block = Block.objects.create(hostel=hostel, name="Block A")
        self.room = Room.objects.create(
            block=block,
            room_number="101",
            room_code="CONCURRENT-A-101",
            capacity=1,
        )

    def test_two_concurrent_requests_cannot_overfill_room(self):
        if connection.vendor != "mysql":
            self.skipTest("This locking test requires MySQL.")

        barrier = threading.Barrier(2)
        outcomes = Queue()

        def attempt_allocation(student_id):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                allocation = allocate_student(
                    student_id=student_id,
                    room_id=self.room.pk,
                )
                outcomes.put(("success", allocation.pk))
            except ValidationError as exc:
                outcomes.put(("rejected", str(exc)))
            except Exception as exc:
                outcomes.put(("error", repr(exc)))
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    attempt_allocation,
                    self.student1.pk,
                ),
                executor.submit(
                    attempt_allocation,
                    self.student2.pk,
                ),
            ]
            for future in futures:
                future.result(timeout=30)

        results = [outcomes.get(timeout=5) for _ in range(2)]
        successes = [item for item in results if item[0] == "success"]
        rejected = [item for item in results if item[0] == "rejected"]
        errors = [item for item in results if item[0] == "error"]

        self.assertEqual(
            errors,
            [],
            msg=f"Unexpected errors during concurrent allocation: {errors}",
        )
        self.assertEqual(len(successes), 1, msg=f"Results: {results}")
        self.assertEqual(len(rejected), 1, msg=f"Results: {results}")

        self.assertEqual(
            Allocation.objects.filter(
                room=self.room,
                status=Allocation.Status.ACTIVE,
            ).count(),
            1,
        )
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

from core.models import (
    Allocation,
    Block,
    Hostel,
    Room,
    Student,
)
from core.services import allocate_student


class Command(BaseCommand):
    help = "Create repeatable demonstration data for the Hostel Management System."

    @transaction.atomic
    def handle(self, *args, **options):
        # Create a hostel and its blocks.
        hostel, _ = Hostel.objects.get_or_create(
            name="Demo Hostel",
            defaults={"address": "Campus Road"},
        )

        block_a, _ = Block.objects.get_or_create(
            hostel=hostel,
            name="Block A",
        )
        block_b, _ = Block.objects.get_or_create(
            hostel=hostel,
            name="Block B",
        )

        # Create rooms with different capacities.
        room_101, _ = Room.objects.get_or_create(
            block=block_a,
            number="101",
            defaults={
                "capacity": 2,
            },
        )
        Room.objects.get_or_create(
            block=block_a,
            number="102",
            defaults={
                "capacity": 3,
            },
        )
        Room.objects.get_or_create(
            block=block_b,
            number="201",
            defaults={
                "capacity": 2,
            },
        )

        demo_users = [
            {
                "username": "demo_student1",
                "email": "student1@example.com",
                "is_staff": False,
            },
            {
                "username": "demo_student2",
                "email": "student2@example.com",
                "is_staff": False,
            },
            {
                "username": "demo_warden",
                "email": "warden@example.com",
                "is_staff": True,
            },
            {
                "username": "demo_admin",
                "email": "hosteladmin@example.com",
                "is_staff": True,
            },
        ]

        created_users = {}
        for details in demo_users:
            username = details["username"]
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": details["email"],
                    "is_staff": details["is_staff"],
                },
            )
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
            created_users[username] = user

        student1, _ = Student.objects.get_or_create(
            student_id="DEMO-STU-001",
            defaults={
                "user": created_users["demo_student1"],
                "full_name": "Demo Student One",
                "email": "student1@example.com",
                "hostel_name": "",
                "room_number": "",
            },
        )
        student2, _ = Student.objects.get_or_create(
            student_id="DEMO-STU-002",
            defaults={
                "user": created_users["demo_student2"],
                "full_name": "Demo Student Two",
                "email": "student2@example.com",
                "hostel_name": "",
                "room_number": "",
            },
        )

        if not Allocation.objects.filter(
            student=student1,
            is_active=True,
        ).exists():
            allocate_student(student1.pk, room_101.pk)

        # Keep the second student as an example of an unallocated student.
        self.stdout.write(
            self.style.SUCCESS(
                "Demo data is ready: 1 hostel, 2 blocks, 3 rooms, "
                "4 users, 2 students, and 1 active allocation."
            )
        )
        self.stdout.write(
            "Demo usernames: demo_student1, demo_student2, "
            "demo_warden, demo_admin"
        )
        self.stdout.write(
            self.style.WARNING(
                "Demo accounts have no usable password until one is set "
                "with the changepassword command."
            )
        )
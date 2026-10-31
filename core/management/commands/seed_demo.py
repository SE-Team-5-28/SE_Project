from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from core.models import (
    Allocation,
    Block,
    Hostel,
    Room,
    Student,
    UserRole,
)


User = get_user_model()


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
                "room_code": "DEMO-A-101",
                "capacity": 2,
                "description": "Double occupancy",
            },
        )
        Room.objects.get_or_create(
            block=block_a,
            number="102",
            defaults={
                "room_code": "DEMO-A-102",
                "capacity": 3,
                "description": "Triple occupancy",
            },
        )
        Room.objects.get_or_create(
            block=block_b,
            number="201",
            defaults={
                "room_code": "DEMO-B-201",
                "capacity": 2,
                "description": "Double occupancy",
            },
        )

        # Create demonstration accounts without hardcoded passwords.
        demo_users = [
            {
                "username": "demo_student1",
                "role": UserRole.Role.STUDENT,
                "email": "student1@example.com",
            },
            {
                "username": "demo_student2",
                "role": UserRole.Role.STUDENT,
                "email": "student2@example.com",
            },
            {
                "username": "demo_warden",
                "role": UserRole.Role.WARDEN,
                "email": "warden@example.com",
            },
            {
                "username": "demo_admin",
                "role": UserRole.Role.HOSTEL_ADMIN,
                "email": "hosteladmin@example.com",
            },
        ]

        created_users = {}
        for details in demo_users:
            username = details["username"]
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": details["email"],
                    "is_active": True,
                },
            )
            created_users[username] = user
            UserRole.objects.update_or_create(
                user=user,
                defaults={"role": details["role"]},
            )

        # Create student profiles.
        student1, _ = Student.objects.get_or_create(
            student_id="DEMO-STU-001",
            defaults={
                "user": created_users["demo_student1"],
                "full_name": "Demo Student One",
                "department": "Computer Science",
                "year_of_study": 2,
            },
        )
        student2, _ = Student.objects.get_or_create(
            student_id="DEMO-STU-002",
            defaults={
                "user": created_users["demo_student2"],
                "full_name": "Demo Student Two",
                "department": "Information Science",
                "year_of_study": 2,
            },
        )

        # Create one active allocation for the first student.
        Allocation.objects.get_or_create(
            student=student1,
            status=Allocation.Status.ACTIVE,
            defaults={
                "room": room_101,
                "check_in_date": None,
            },
        )

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
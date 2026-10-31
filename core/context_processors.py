from .models import User, get_user_role


def user_role(request):
    role = get_user_role(request.user)
    return {
        "user_role": role,
        "role_label": dict(User.Role.choices).get(role, role),
        "is_staff_role": role in {
            User.Role.WARDEN,
            User.Role.HOSTEL_ADMIN,
            User.Role.SYSTEM_ADMIN,
        },
    }

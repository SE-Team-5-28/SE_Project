from functools import wraps

from django.core.exceptions import PermissionDenied

from .models import get_user_role


def role_required(*allowed_roles):
    """Restrict a view to authenticated users with an allowed role."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                # Let Django's login_required behavior handle anonymous users.
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(
                    request.get_full_path(),
                    login_url="login",
                )

            if get_user_role(request.user) not in allowed_roles:
                raise PermissionDenied(
                    "You do not have permission to access this page."
                )

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator
from rest_framework.permissions import BasePermission, SAFE_METHODS


class PackPermission(BasePermission):
    """
    GET/HEAD/OPTIONS:
        accessible to the frontend.

    POST/PUT/PATCH/DELETE:
        only Django staff/superuser.
    """

    message = "Only an administrator can create, edit or delete packs."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        user = getattr(request, "user", None)

        return bool(
            user
            and user.is_authenticated
            and (
                getattr(user, "is_staff", False)
                or getattr(user, "is_superuser", False)
            )
        )

from django.core.exceptions import ObjectDoesNotExist


def get_student(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    if user.__class__.__name__ == "Student":
        return user

    try:
        return user.student
    except (AttributeError, ObjectDoesNotExist):
        return None

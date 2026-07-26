from rest_framework.pagination import (
    PageNumberPagination,
)


class ExerciseBacPagination(
    PageNumberPagination
):
    """
    Un seul exercice est envoyé par défaut.
    """

    page_size = 1

    page_size_query_param = "page_size"

    max_page_size = 5

    page_query_param = "page"
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.generics import GenericAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course.models import Branch, Chapter
from exercise_bac.models import ExerciseBac
from exercise_bac.serializers import (
    ExerciseBacDetailSerializer,
    ExerciseBacListSerializer,
)


class BacExercisePagination(PageNumberPagination):
    """
    On ne charge qu'un petit lot de métadonnées à la fois.
    Le contenu JSON complet n'est jamais lu par cet endpoint.
    """

    page_size = 8
    page_size_query_param = "page_size"
    max_page_size = 20


class ExerciseBacByChapterView(GenericAPIView):
    """
    Liste PAGINÉE et légère des exercices d'un chapitre.

    GET /api/bac/exercises/chapter/12/?page=1&page_size=8
    GET /api/bac/exercises/chapter/12/?branch_code=math&year=2024&page=1

    Cette vue ne sérialise jamais content. C'est le point essentiel qui évite
    de transférer tous les SVG, questions et solutions au premier affichage.
    """

    serializer_class = ExerciseBacListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = BacExercisePagination

    def get_queryset(self):
        return (
            ExerciseBac.objects
            .select_related("chapter", "chapter__subject")
            .prefetch_related("branches")
            .filter(is_active=True)
            # Le champ JSON peut être très lourd. Ne surtout pas le charger ici.
            .defer("content")
            .order_by("-year", "exercise_number", "id")
        )

    @staticmethod
    def _parse_year(request):
        raw = str(request.query_params.get("year", "")).strip()
        if not raw or raw.lower() == "all":
            return None

        try:
            year = int(raw)
        except (TypeError, ValueError):
            return None

        return year if 1900 <= year <= 2200 else None

    def get(self, request, chapter_id):
        chapter = get_object_or_404(
            Chapter.objects.select_related("subject"),
            id=chapter_id,
        )

        branch_code = (
            str(request.query_params.get("branch_code", ""))
            .strip()
            .lower()
        )
        if branch_code == "all":
            branch_code = ""

        selected_year = self._parse_year(request)

        chapter_exercises = self.get_queryset().filter(chapter_id=chapter.id)
        chapter_total_count = chapter_exercises.count()
        exercises = chapter_exercises

        selected_branch = None
        if branch_code:
            selected_branch = get_object_or_404(Branch, code=branch_code)
            exercises = exercises.filter(branches__code=branch_code)

        if selected_year is not None:
            exercises = exercises.filter(year=selected_year)

        exercises = exercises.distinct()

        # Années disponibles. Si une branche est sélectionnée, on ne renvoie
        # que les années réellement disponibles pour cette branche.
        years_queryset = chapter_exercises
        if branch_code:
            years_queryset = years_queryset.filter(branches__code=branch_code)

        available_years = list(
            years_queryset
            .values_list("year", flat=True)
            .distinct()
            .order_by("-year")
        )

        # Branches disponibles + nombre d'exercices. Le compteur respecte
        # l'année sélectionnée afin que l'UI affiche des nombres cohérents.
        branch_filter = Q(
            bac_exercises__chapter_id=chapter.id,
            bac_exercises__is_active=True,
        )
        if selected_year is not None:
            branch_filter &= Q(bac_exercises__year=selected_year)

        all_branches_queryset = chapter_exercises
        if selected_year is not None:
            all_branches_queryset = all_branches_queryset.filter(year=selected_year)
        all_branches_count = all_branches_queryset.count()

        available_branches = list(
            Branch.objects
            .filter(
                bac_exercises__chapter_id=chapter.id,
                bac_exercises__is_active=True,
            )
            .annotate(
                exercise_count=Count(
                    "bac_exercises",
                    filter=branch_filter,
                    distinct=True,
                )
            )
            .filter(exercise_count__gt=0)
            .order_by("name", "code")
            .values("id", "code", "name", "exercise_count")
            .distinct()
        )

        paginator = self.pagination_class()
        page_items = paginator.paginate_queryset(exercises, request, view=self)
        serializer = self.get_serializer(page_items, many=True)

        page = paginator.page
        total_count = page.paginator.count

        return Response(
            {
                "chapter": {
                    "id": chapter.id,
                    "code": chapter.code,
                    "title": chapter.title,
                },
                "branch": (
                    {
                        "id": selected_branch.id,
                        "code": selected_branch.code,
                        "name": selected_branch.name,
                    }
                    if selected_branch
                    else None
                ),
                "filters": {
                    "branch_code": branch_code or None,
                    "year": selected_year,
                },
                "available_branches": available_branches,
                "available_years": available_years,
                "chapter_total_count": chapter_total_count,
                "all_branches_count": all_branches_count,
                # Compatibilité avec l'ancien frontend.
                "count": total_count,
                "pagination": {
                    "page": page.number,
                    "page_size": paginator.get_page_size(request),
                    "total_count": total_count,
                    "total_pages": page.paginator.num_pages,
                    "has_next": page.has_next(),
                    "has_previous": page.has_previous(),
                    "next_page": page.next_page_number() if page.has_next() else None,
                    "previous_page": (
                        page.previous_page_number()
                        if page.has_previous()
                        else None
                    ),
                },
                "exercises": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class ExerciseBacDetailView(RetrieveAPIView):
    """
    Charge le JSON complet d'UN exercice uniquement.

    Le frontend appelle cet endpoint au moment où l'exercice devient courant,
    puis le garde dans un cache mémoire. Ainsi un retour vers l'exercice ne
    déclenche pas de nouveau téléchargement.
    """

    serializer_class = ExerciseBacDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "exercise_id"

    def get_queryset(self):
        return (
            ExerciseBac.objects
            .select_related("chapter", "chapter__subject")
            .prefetch_related("branches")
            .filter(is_active=True)
        )

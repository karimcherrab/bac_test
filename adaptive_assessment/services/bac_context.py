from adaptive_assessment.models import BacIdea


def get_axis_bac_ideas(*, axis, branch):
    """Return only BAC ideas with documented historical occurrences."""

    ideas = (
        BacIdea.objects
        .filter(
            axis=axis,
            branch=branch,
            is_active=True,
            occurrence_count__gt=0,
        )
        .prefetch_related("variants")
        .order_by("-occurrence_count", "code")
    )

    result = []

    for idea in ideas:
        variants = [
            {
                "id": variant.id,
                "code": variant.code,
                "title": variant.title,
                "description": variant.description,
                "years": variant.years or [],
                "occurrence_count": int(variant.occurrence_count or 0),
                "difficulty": variant.difficulty,
                "distinguishing_feature": variant.distinguishing_feature,
            }
            for variant in idea.variants.all()
            if variant.is_active and int(variant.occurrence_count or 0) > 0
        ]

        result.append(
            {
                "id": idea.id,
                "code": idea.code,
                "title": idea.title,
                "description": idea.description,
                "priority": idea.priority,
                "frequency_level": idea.frequency_level,
                "occurrence_count": int(idea.occurrence_count or 0),
                "years": idea.years or [],
                "bac_occurrences": idea.bac_occurrences or [],
                "variants": variants,
            }
        )

    return result

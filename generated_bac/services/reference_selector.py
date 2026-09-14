import random
from exercise_bac.models import ExerciseBac
from .exceptions import NoReferenceExercisesError
from .math_visuals import without_svg


class BacReferenceSelector:
    def select(self, *, chapter_id, branch_code, limit=1, strategy="random", exclude_ids=(), subject_code="math"):
        qs = ExerciseBac.objects.filter(chapter_id=chapter_id, branches__code=branch_code, is_active=True).distinct()
        ids = list(qs.values_list("id", flat=True))
        if not ids:
            raise NoReferenceExercisesError("لا يوجد تمرين مرجعي لهذه الوحدة والشعبة. أضف تمرين رياضيات واحدًا على الأقل.")
        pool = [pk for pk in ids if pk not in exclude_ids] or ids
        if subject_code == "natural_sciences":
            from .science_documents import build_catalog
            from .exceptions import AIResponseError
            random.shuffle(pool)
            remaining=[pk for pk in ids if pk not in pool]
            random.shuffle(remaining)
            for pk in pool+remaining:
                candidate=qs.get(pk=pk)
                try:build_catalog(candidate.content)
                except AIResponseError:continue
                return [candidate]
            raise NoReferenceExercisesError("لا توجد وثائق علوم موصوفة بما يكفي لهذه الوحدة والشعبة. أكمل metadata للصور الموجودة.")
        return [qs.get(pk=random.choice(pool))]

    def compact_for_exercise_generation(self, exercises):
        result=[]
        for ex in exercises:
            content = ex.content if isinstance(ex.content, dict) else {}
            from .reference_payload import compact_content
            result.append({"database_id":ex.pk,"title":ex.title,"content":compact_content(content)})
        return result

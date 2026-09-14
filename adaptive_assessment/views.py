import json

from django.conf import settings
import uuid

from django.core.files.storage import default_storage
from django.http import FileResponse

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AdaptiveAnswer, AdaptiveTest, AdaptiveTestQuestion, BacIdea
from .serializers import (
    AdaptiveAnswerSerializer,
    AdaptiveTestHistorySerializer,
    AdaptiveTestSerializer,
    StudentBacIdeaMasterySerializer,
    StudentSkillMasterySerializer,
)
from .services.answer_evaluator import AnswerEvaluationError, TeacherAnswerEvaluator
from .services.image_utils import (
    SolutionImageError,
    delete_persisted_images,
    persist_solution_images,
    prepare_solution_images,
)
from .services.vision_answer_evaluator import (
    VisionAnswerEvaluationError,
    VisionAnswerUnreadable,
    VisionTeacherAnswerEvaluator,
)
from .services.blueprint import BlueprintGenerator
from .services.mastery import update_mastery_from_answer
from .services.test_builder import AdaptiveTestBuilder, QuestionGenerationFailed
from .services.idea_explorer import IdeaExplorerService


def _student_for_request(request):
    return getattr(request.user, "student", None) or request.user


def _resolve_axis_branch(axis_id, branch_id):
    AxisModel = AdaptiveTest._meta.get_field("axis").remote_field.model
    BranchModel = AdaptiveTest._meta.get_field("branch").remote_field.model
    return (
        get_object_or_404(AxisModel, pk=axis_id),
        get_object_or_404(BranchModel, pk=branch_id),
    )


def _test_queryset():
    return (
        AdaptiveTest.objects
        .select_related("axis", "branch")
        .prefetch_related(
            "test_questions",
            "test_questions__skill",
            "test_questions__bac_idea",
            "test_questions__bac_idea__variants",
            "test_questions__variant",
            "test_questions__answer",
        )
    )


def _sequence_progress(test):
    blueprint = test.blueprint or {}
    slots = list(blueprint.get("slots") or [])
    runtime = dict(blueprint.get("runtime") or {})
    cursor = min(int(runtime.get("cursor_index") or 0), len(slots))
    current = slots[cursor] if cursor < len(slots) else None

    def slot_label(slot):
        if not slot:
            return ""
        if slot.get("source_type") == "skill":
            return slot.get("skill_idea_name") or slot.get("skill_idea_code") or "فكرة من المحور"
        return (
            slot.get("variant_title")
            or slot.get("bac_idea_title")
            or slot.get("variant_code")
            or slot.get("bac_idea_code")
            or "فكرة بكالوريا"
        )

    return {
        "total_targets": len(slots),
        "completed_targets": cursor,
        "remaining_targets": max(len(slots) - cursor, 0),
        "current_target_number": cursor + 1 if current else len(slots),
        "current_target": current,
        "current_target_label": slot_label(current),
        "current_difficulty": current.get("difficulty") if current else None,
        "progress_percentage": round((cursor / max(len(slots), 1)) * 100.0, 2),
        "axis_mastered": bool(slots) and cursor >= len(slots),
        "generated_attempts": int(runtime.get("generated_attempts") or 0),
        "attempts_by_target": runtime.get("attempts_by_target") or {},
    }


def _misconception_context(question):
    output = []
    if question.skill_id:
        output.extend(
            {"code": item.code, "description": item.description}
            for item in question.skill.misconceptions.all()
            if item.is_active
        )
    if question.bac_idea_id:
        output.extend(
            {"code": item.code, "description": item.description}
            for item in question.bac_idea.misconceptions.all()
            if item.is_active
        )
    # Preserve order while removing duplicates.
    seen = set()
    clean = []
    for item in output:
        code = item.get("code")
        if code and code not in seen:
            seen.add(code)
            clean.append(item)
    return clean


def _transition_payload(*, question, answer):
    # Only update deterministic sequence state here. No Groq generation.
    AdaptiveTestBuilder().advance_after_answer(
        question.test,
        was_correct=bool(answer.is_correct),
    )

    test = _test_queryset().get(pk=question.test_id)
    progress = _sequence_progress(test)

    practice_mode = (test.blueprint or {}).get("mode") == "idea_practice"

    if answer.is_correct:
        if progress["axis_mastered"] and practice_mode:
            transition_message = "ممتاز، أتقنت هذه الفكرة في جلسة التدريب الحالية."
        else:
            transition_message = (
                "أحسنت، أتقنت هذه الفكرة. ننتقل الآن إلى الفكرة التالية."
                if not progress["axis_mastered"]
                else "ممتاز، أتقنت جميع أفكار المحور وأفكار البكالوريا المطلوبة."
            )
        action = "advance" if not progress["axis_mastered"] else "completed"
    else:
        transition_message = (
            "هذه الفكرة لم تُتقن بعد. راجع تصحيح الأستاذ، ثم سنعطيك تمريناً جديداً "
            "لنفس الفكرة قبل الانتقال إلى غيرها."
        )
        action = "retry_same_target"

    return {
        "answer": AdaptiveAnswerSerializer(answer).data,
        "test": AdaptiveTestSerializer(test).data,
        "sequence_progress": progress,
        "action": action,
        "transition_message": transition_message,
        "next_question_ready": bool(
            test.test_questions.filter(answer__isnull=True, is_validated=True).exists()
        ),
    }


class BlueprintPreviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, axis_id):
        student = _student_for_request(request)
        branch_id = request.data.get("branch_id")
        if not branch_id:
            return Response({"detail": "branch_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        axis, branch = _resolve_axis_branch(axis_id, branch_id)
        blueprint = BlueprintGenerator(student=student, axis=axis, branch=branch).build()
        return Response(blueprint)


class AxisIdeaExplorerView(APIView):
    """Return every documented BAC idea with historical + personal mastery statistics."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, axis_id):
        student = _student_for_request(request)
        branch_id = request.query_params.get("branch_id")
        if not branch_id:
            return Response(
                {"detail": "branch_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        axis, branch = _resolve_axis_branch(axis_id, branch_id)
        payload = IdeaExplorerService().dashboard(
            student=student,
            axis=axis,
            branch=branch,
        )
        return Response(payload)


class StartIdeaPracticeView(APIView):
    """Create a one-target practice session for the BAC idea selected by the student."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, axis_id, idea_id):
        student = _student_for_request(request)
        branch_id = request.data.get("branch_id")
        if not branch_id:
            return Response(
                {"detail": "branch_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        axis, branch = _resolve_axis_branch(axis_id, branch_id)
        idea = get_object_or_404(
            BacIdea.objects.prefetch_related("variants", "misconceptions"),
            pk=idea_id,
            axis=axis,
            branch=branch,
            is_active=True,
            occurrence_count__gt=0,
        )

        try:
            blueprint = IdeaExplorerService().build_practice_blueprint(
                student=student,
                axis=axis,
                branch=branch,
                idea=idea,
                variant_id=request.data.get("variant_id"),
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # No DB migration is needed: existing mode='remedial' is retained while
        # blueprint.mode tells the UI this is a focused idea-practice session.
        test = AdaptiveTest.objects.create(
            student=student,
            axis=axis,
            branch=branch,
            mode="remedial",
            status="draft",
            blueprint=blueprint,
        )

        try:
            AdaptiveTestBuilder().start_test(test)
        except QuestionGenerationFailed as exc:
            test.status = "draft"
            test.save(update_fields=["status", "updated_at"])
            return Response(
                {
                    "detail": str(exc),
                    "test_id": test.id,
                    "retryable": True,
                    "notice": "تم حفظ جلسة الفكرة؛ أعد محاولة توليد نفس التمرين دون فقد التقدم.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        test = _test_queryset().get(pk=test.pk)
        data = AdaptiveTestSerializer(test).data
        data["sequence_progress"] = _sequence_progress(test)
        data["practice_focus"] = blueprint.get("focus") or {}
        data["notice"] = (
            "أنت الآن تتدرب على الفكرة التي اخترتها فقط. إذا أخطأت سيُنشأ تمرين جديد "
            "لنفس الفكرة حتى تتقنها."
        )
        return Response(data, status=status.HTTP_201_CREATED)


class GenerateAxisTestView(APIView):
    """Create the sequence but generate only the FIRST current exercise."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, axis_id):
        student = _student_for_request(request)
        branch_id = request.data.get("branch_id")
        if not branch_id:
            return Response({"detail": "branch_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        axis, branch = _resolve_axis_branch(axis_id, branch_id)
        blueprint = BlueprintGenerator(student=student, axis=axis, branch=branch).build()

        test = AdaptiveTest.objects.create(
            student=student,
            axis=axis,
            branch=branch,
            mode="full",
            status="draft",
            blueprint=blueprint,
        )

        # Empty blueprint means there are no unmastered targets left.
        if not blueprint.get("slots"):
            test.status = "completed"
            test.score = 100.0
            test.mastery_score = 100.0
            test.save(update_fields=["status", "score", "mastery_score", "updated_at"])
            test = _test_queryset().get(pk=test.pk)
            data = AdaptiveTestSerializer(test).data
            data["sequence_progress"] = _sequence_progress(test)
            data["notice"] = "لقد أتقنت جميع أفكار هذا المحور وأفكار البكالوريا المرتبطة به."
            return Response(data, status=status.HTTP_201_CREATED)

        try:
            AdaptiveTestBuilder().start_test(test)
        except QuestionGenerationFailed as exc:
            # Keep the test draft so the same first idea can be retried later.
            test.status = "draft"
            test.save(update_fields=["status", "updated_at"])
            return Response(
                {
                    "detail": str(exc),
                    "test_id": test.id,
                    "retryable": True,
                    "notice": "لم نحذف أي فكرة. سنعيد تحضير نفس التمرين عند المحاولة التالية.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        test = _test_queryset().get(pk=test.pk)
        data = AdaptiveTestSerializer(test).data
        data["sequence_progress"] = _sequence_progress(test)
        data["notice"] = (
            "سيتم اختبارك فكرةً بفكرة من الأسهل إلى الأصعب. "
            "إذا أخطأت سنعطيك تمريناً جديداً لنفس الفكرة حتى تتقنها، ثم ننتقل للفكرة التالية."
        )
        return Response(data, status=status.HTTP_201_CREATED)


class GenerateCurrentQuestionView(APIView):
    """Retry/resume generation for the current target only."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, test_id):
        student = _student_for_request(request)
        test = get_object_or_404(AdaptiveTest, pk=test_id, student=student)

        if test.status == "completed":
            test = _test_queryset().get(pk=test.pk)
            data = AdaptiveTestSerializer(test).data
            data["sequence_progress"] = _sequence_progress(test)
            return Response(data)

        last_question = (
            test.test_questions.select_related("answer")
            .order_by("-order")
            .first()
        )
        retry_reason = ""
        force_new = False
        if last_question is not None and hasattr(last_question, "answer"):
            force_new = True
            retry_reason = (
                "next_target"
                if last_question.answer.is_correct
                else "same_target_new_exercise_after_incorrect_answer"
            )

        try:
            AdaptiveTestBuilder().ensure_current_question(
                test,
                force_new=force_new,
                retry_reason=retry_reason,
            )
        except QuestionGenerationFailed as exc:
            return Response(
                {"detail": str(exc), "retryable": True, "test_id": test.id},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        test = _test_queryset().get(pk=test.pk)
        data = AdaptiveTestSerializer(test).data
        data["sequence_progress"] = _sequence_progress(test)
        return Response(data)


class AxisTestHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, axis_id):
        student = _student_for_request(request)
        branch_id = request.query_params.get("branch_id")
        tests = (
            AdaptiveTest.objects
            .filter(student=student, axis_id=axis_id)
            .exclude(status="failed")
            .select_related("axis", "branch")
            .annotate(
                question_count_value=Count("test_questions", distinct=True),
                answered_count_value=Count(
                    "test_questions",
                    filter=Q(test_questions__answer__isnull=False),
                    distinct=True,
                ),
                correct_count_value=Count(
                    "test_questions",
                    filter=Q(test_questions__answer__is_correct=True),
                    distinct=True,
                ),
            )
            .order_by("-created_at", "-id")
        )
        if branch_id:
            tests = tests.filter(branch_id=branch_id)
        return Response(AdaptiveTestHistorySerializer(tests[:30], many=True).data)


class AdaptiveTestDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, test_id):
        student = _student_for_request(request)
        test = get_object_or_404(_test_queryset(), pk=test_id, student=student)
        data = AdaptiveTestSerializer(test).data
        data["sequence_progress"] = _sequence_progress(test)
        return Response(data)


class SubmitTestQuestionView(APIView):
    """Correct as a teacher, then stay on the idea or advance to the next one."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, test_question_id):
        student = _student_for_request(request)
        question = get_object_or_404(
            AdaptiveTestQuestion.objects
            .select_related("test", "test__axis", "test__branch", "skill", "bac_idea", "variant")
            .prefetch_related("skill__misconceptions", "bac_idea__misconceptions"),
            pk=test_question_id,
            test__student=student,
            is_validated=True,
        )

        if hasattr(question, "answer"):
            return Response(
                {"detail": "تمت الإجابة عن هذا التمرين مسبقاً."},
                status=status.HTTP_409_CONFLICT,
            )

        submitted = request.data.get("answer")
        if submitted in (None, "", {}):
            top_steps = request.data.get("steps")
            if top_steps:
                submitted = {"format": "math_steps", "steps": top_steps}

        if not isinstance(submitted, dict):
            return Response(
                {"detail": "يجب إرسال الحل على شكل خطوات."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        steps = submitted.get("steps", [])
        if not isinstance(steps, list) or not any(
            (
                str(item.get("latex", "")).strip()
                or str(item.get("text", item.get("explanation", ""))).strip()
            )
            if isinstance(item, dict)
            else str(item).strip()
            for item in steps
        ):
            return Response(
                {"detail": "اكتب خطوة واحدة على الأقل في الحل."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        misconception_context = _misconception_context(question)

        try:
            evaluation = TeacherAnswerEvaluator().evaluate(
                question_payload=question.question,
                student_answer=submitted,
                target_skill_idea_codes=question.target_skill_idea_codes,
                allowed_misconceptions=misconception_context,
            )
        except AnswerEvaluationError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "retryable": True,
                    "notice": "لم تُسجل إجابتك كخاطئة؛ أعد إرسالها بعد لحظات.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            return Response(
                {
                    "detail": "تعذر التصحيح مؤقتاً. أعد المحاولة دون تغيير إجابتك.",
                    "retryable": True,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        teacher_feedback = evaluation["feedback"]
        answer = AdaptiveAnswer.objects.create(
            test_question=question,
            student=student,
            answer={"format": "math_steps", "steps": steps},
            is_correct=evaluation["is_correct"],
            score=evaluation["score"],
            feedback=json.dumps(teacher_feedback, ensure_ascii=False),
            detected_misconception_codes=evaluation["detected_misconception_codes"],
            time_spent_seconds=max(0, int(request.data.get("time_spent_seconds", 0) or 0)),
            hints_used=max(0, int(request.data.get("hints_used", 0) or 0)),
            solution_viewed=bool(request.data.get("solution_viewed", False)),
        )
        update_mastery_from_answer(answer)

        payload = _transition_payload(question=question, answer=answer)
        return Response(payload, status=status.HTTP_201_CREATED)


class SubmitImageSolutionView(APIView):
    """Read 1..5 photographed solution pages, grade them, then reuse normal mastery."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, test_question_id):
        student = _student_for_request(request)
        question = get_object_or_404(
            AdaptiveTestQuestion.objects
            .select_related("test", "test__axis", "test__branch", "skill", "bac_idea", "variant")
            .prefetch_related("skill__misconceptions", "bac_idea__misconceptions"),
            pk=test_question_id,
            test__student=student,
            is_validated=True,
        )

        if hasattr(question, "answer"):
            return Response(
                {"detail": "تمت الإجابة عن هذا التمرين مسبقاً."},
                status=status.HTTP_409_CONFLICT,
            )

        uploaded = request.FILES.getlist("images")
        if not uploaded and request.FILES.get("image"):
            uploaded = [request.FILES["image"]]

        try:
            prepared = prepare_solution_images(uploaded)
        except SolutionImageError as exc:
            return Response(
                {"detail": str(exc), "retake_required": True},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            evaluation = VisionTeacherAnswerEvaluator().evaluate(
                question_payload=question.question,
                prepared_images=prepared,
                target_skill_idea_codes=question.target_skill_idea_codes,
                allowed_misconceptions=_misconception_context(question),
            )
        except VisionAnswerUnreadable as exc:
            # Crucial: no AdaptiveAnswer and no mastery update for unreadable photos.
            return Response(
                {
                    "detail": str(exc),
                    "retake_required": True,
                    "image_quality_notes": exc.quality_notes,
                    "notice": "لم تُحسب هذه المحاولة ولم يتغير تقدمك. أعد تصوير الحل بوضوح.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except VisionAnswerEvaluationError as exc:
            payload = {
                "detail": str(exc),
                "retryable": True,
                "notice": "لم تُسجل المحاولة كإجابة خاطئة؛ صورك ما زالت في جهازك ويمكنك إعادة الإرسال.",
                "vision_status": "temporarily_unavailable",
            }
            # In local development only, return a sanitized provider diagnostic.
            # This is exactly what is needed to discover whether Groq returned
            # 400/401/403/429/etc. Production never exposes it.
            if settings.DEBUG:
                payload["debug"] = {
                    "provider_status": getattr(exc, "provider_status", None),
                    "provider_detail": getattr(exc, "provider_detail", "")[:2000],
                }
            return Response(
                payload,
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            return Response(
                {
                    "detail": "تعذر تصحيح الحل المصوّر مؤقتاً. لم تتغير نتيجة الإتقان.",
                    "retryable": True,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Persist only AFTER the vision model confirms the pages are readable.
        records = []
        submission_token = f"q{question.id}_{uuid.uuid4().hex[:12]}"
        try:
            records = persist_solution_images(
                prepared_images=prepared,
                student_id=getattr(student, "pk", None),
                answer_id=submission_token,
            )
            answer = AdaptiveAnswer.objects.create(
                test_question=question,
                student=student,
                answer={
                    "format": "image_solution",
                    "images": records,
                    "page_count": len(records),
                },
                is_correct=evaluation["is_correct"],
                score=evaluation["score"],
                feedback=json.dumps(evaluation["feedback"], ensure_ascii=False),
                detected_misconception_codes=evaluation["detected_misconception_codes"],
                time_spent_seconds=max(0, int(request.data.get("time_spent_seconds", 0) or 0)),
                hints_used=max(0, int(request.data.get("hints_used", 0) or 0)),
                solution_viewed=str(request.data.get("solution_viewed", "")).lower() in {"1", "true", "yes"},
            )
        except Exception:
            delete_persisted_images(records)
            return Response(
                {
                    "detail": "تم التصحيح لكن تعذر حفظ المحاولة. لم يتغير تقدمك؛ أعد الإرسال.",
                    "retryable": True,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        update_mastery_from_answer(answer)
        payload = _transition_payload(question=question, answer=answer)
        payload["answer_mode"] = "image"
        return Response(payload, status=status.HTTP_201_CREATED)


class AdaptiveAnswerImageView(APIView):
    """Authenticated access to a student's stored solution page."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, answer_id, page):
        student = _student_for_request(request)
        answer = get_object_or_404(
            AdaptiveAnswer.objects.select_related("test_question", "test_question__test"),
            pk=answer_id,
            student=student,
            test_question__test__student=student,
        )
        payload = answer.answer if isinstance(answer.answer, dict) else {}
        images = payload.get("images") or []
        record = next(
            (item for item in images if isinstance(item, dict) and int(item.get("page") or 0) == int(page)),
            None,
        )
        if not record:
            return Response({"detail": "الصورة غير موجودة."}, status=status.HTTP_404_NOT_FOUND)
        name = str(record.get("storage_name") or "")
        if not name.startswith("adaptive_answers/") or not default_storage.exists(name):
            return Response({"detail": "الصورة غير موجودة."}, status=status.HTTP_404_NOT_FOUND)

        response = FileResponse(default_storage.open(name, "rb"), content_type="image/jpeg")
        response["Content-Disposition"] = f'inline; filename="solution-page-{int(page)}.jpg"'
        response["Cache-Control"] = "private, max-age=300"
        return response


class AdaptiveTestResultView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, test_id):
        student = _student_for_request(request)
        test = get_object_or_404(_test_queryset(), pk=test_id, student=student)
        data = AdaptiveTestSerializer(test).data
        data["sequence_progress"] = _sequence_progress(test)
        return Response(data)


class AxisProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, axis_id):
        student = _student_for_request(request)
        skill_qs = (
            student.skill_masteries
            .filter(skill__axis_id=axis_id)
            .select_related("skill")
        )
        bac_qs = (
            student.bac_idea_masteries
            .filter(bac_idea__axis_id=axis_id)
            .select_related("bac_idea")
        )
        return Response(
            {
                "axis_id": axis_id,
                "skills": StudentSkillMasterySerializer(skill_qs, many=True).data,
                "bac_ideas": StudentBacIdeaMasterySerializer(bac_qs, many=True).data,
                "weak_skill_ideas": [
                    {"skill_code": item.skill.code, "idea_codes": item.weak_idea_codes or []}
                    for item in skill_qs
                    if item.weak_idea_codes
                ],
                "weak_bac_variants": [
                    {
                        "bac_idea_code": item.bac_idea.code,
                        "variant_codes": item.weak_variant_codes or [],
                    }
                    for item in bac_qs
                    if item.weak_variant_codes
                ],
            }
        )

"""One validated question per HTTP request, private persisted checkpoints."""
import copy
import hashlib
import json
import uuid
from django.db import transaction
from .exceptions import AIResponseError
from .math_visuals import without_svg
from .science_prompt_builder import SciencePromptBuilder
from .science_documents import validate_solution as validate_science_solution
from .validators import SolutionValidator


def fingerprint(exercise):
    return hashlib.sha256(json.dumps(exercise,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def one_question_context(exercise,index):
    context=without_svg(copy.deepcopy(exercise))
    # Keep all givens and previous question texts for references such as 'deduce'.
    all_questions=context['questions']
    context['questions']=[all_questions[index]]
    context['preceding_questions']=[{'id':q['id'],'text':q['text']} for q in all_questions[:index]]
    return context


def advance(service, record, regenerate=False):
    from ..models import GeneratedBacExercise
    with transaction.atomic():
        current=GeneratedBacExercise.objects.select_for_update().get(pk=record.pk)
        if current.solution and not regenerate and not (current.generation_metadata or {}).get("solution_draft"):return current
        exercise=current.exercise
        if not isinstance(exercise,dict) or not exercise.get('questions'):raise AIResponseError('التمرين لا يحتوي أسئلة صالحة.')
        metadata=dict(current.generation_metadata or {})
        draft=metadata.get('solution_draft',{})
        digest=fingerprint(exercise)
        if regenerate or draft.get('fingerprint')!=digest:
            draft={'revision':uuid.uuid4().hex,'fingerprint':digest,'questions':[],'models':[]}
            metadata['solution_draft']=draft
            current.generation_metadata=metadata
            # Existing complete solution remains available until replacement is complete.
            current.save(update_fields=['generation_metadata','updated_at'])
        revision=draft['revision']; index=len(draft['questions']); previous=copy.deepcopy(draft['questions'])
    service._configure_saved_subject(current)
    context=one_question_context(exercise,index)
    builder=service.prompt_builder
    catalog=None
    if isinstance(builder,SciencePromptBuilder):
        selected=set(context['questions'][0]['document_refs'])
        catalog=[d for d in builder.catalog if d['id'] in selected or selected.intersection(d.get('linked_document_ids',[]))]
        builder=SciencePromptBuilder(catalog)
    system,user=builder.build_solution_prompt(generated_exercise_id=current.pk,exercise=context)
    user+='\nأجب عن السؤال الوحيد في questions. لا تحل بقية الأسئلة. من 2 إلى 6 خطوات واضحة مع الرسم المطلوب فقط؛ لا تكرر المعطيات أو SVG.'
    user+='\nنتائج الأسئلة السابقة للاستعمال دون إعادة حلها: '+json.dumps(
        [{'question_id':q['question_id'],'final_answer':q['final_answer']} for q in previous],ensure_ascii=False)
    if catalog is not None:
        validator=lambda data:validate_science_solution(data,catalog=catalog,exercise=context,exercise_id=current.pk)
    else:
        validator=lambda data:SolutionValidator().validate(data,exercise=context,exercise_id=current.pk)
    answer,model=service.validated_request(system_prompt=system,user_prompt=user,validator=validator,max_tokens=3200)
    with transaction.atomic():
        current=GeneratedBacExercise.objects.select_for_update().get(pk=record.pk)
        metadata=dict(current.generation_metadata or {});draft=metadata.get('solution_draft',{})
        if metadata.get('solution_completed_revision')==revision:return current
        if draft.get('revision')!=revision or fingerprint(current.exercise)!=digest:
            raise AIResponseError('تغير التمرين أثناء الحل؛ أعد الطلب لاستعمال أحدث نسخة.')
        if len(draft['questions'])!=index:return current  # Another request already checkpointed this question.
        draft['questions'].append(answer['questions'][0]);draft['models'].append(model)
        metadata['solution_draft']=draft
        if len(draft['questions'])==len(exercise['questions']):
            current.solution={'exercise_id':current.pk,'general_strategy':'نحل الأسئلة بالترتيب مع استعمال النتائج السابقة.','questions':draft['questions']}
            current.model_solution=model;current.status='solution_ready';current.generation_error=''
            metadata['solution_completed_revision']=revision
            metadata.pop('solution_draft',None)
        current.generation_metadata=metadata
        current.save(update_fields=['generation_metadata','solution','model_solution','status','generation_error','updated_at'])
    return current


def progress(record):
    draft=(record.generation_metadata or {}).get('solution_draft')
    total=len((record.exercise or {}).get('questions',[]))
    if draft:return {'completed':len(draft.get('questions',[])),'total':total,'complete':False}
    return {'completed':total if record.solution else 0,'total':total,'complete':bool(record.solution)}

"""Read existing course models. MemoryLesson is only an internal practice snapshot."""
import json
import re
from django.apps import apps
from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404
from .models import MemoryLesson
from .ai import PracticeError


def model(name, default):
    return apps.get_model(getattr(settings, name, default))


def subject_key(subject):
    code = str(subject.code).strip().lower()
    overrides = getattr(settings, 'MEMORY_SUBJECT_CODES', {})
    if code in overrides:
        return overrides[code]
    name = re.sub('[إأآ]', 'ا', str(subject.name)).lower()
    if code in ('islamic', 'islamic_education', 'islamic_sciences', 'islam') or 'اسلام' in name or 'شريعة' in name:
        return 'islamic'
    if code in ('history', 'histoire') or 'تاريخ' in name:
        return 'history'
    if code in ('physics', 'physique') or 'فيزياء' in name:
        return 'physics'
    if code in ('math', 'maths', 'mathematics') or 'رياضيات' in name:
        return 'math'
    if code in ('science', 'natural_sciences', 'svt') or 'طبيعة' in name or 'تجريبية' in name:
        return 'science'
    return code


def positive(value, label):
    try:
        n = int(value)
        if n < 1: raise ValueError()
        return n
    except (TypeError, ValueError):
        raise PracticeError('معرف غير صالح: ' + label, 400)


def chapter_context(chapter_id):
    chapter = get_object_or_404(model('MEMORY_CHAPTER_MODEL', 'course.Chapter').objects.select_related('subject'), pk=positive(chapter_id, 'الوحدة'), is_active=True)
    key = subject_key(chapter.subject)
    return {'chapter_id': chapter.pk, 'chapter_title': chapter.title,
            'subject_code': key, 'subject_name': chapter.subject.name,
            'practice_mode': 'memory' if key in ('islamic', 'history') else 'standard'}


def axes(chapter_id=None, branch=''):
    qs = model('MEMORY_AXIS_MODEL', 'course.Axis').objects.filter(is_active=True, chapter__is_active=True).select_related('chapter__subject')
    if chapter_id:
        qs = qs.filter(chapter_id=positive(chapter_id, 'الوحدة'))
    if branch:
        qs = qs.filter(Q(branches__code=branch) | Q(branches__isnull=True)).distinct()
    return qs.order_by('order', 'pk')


def decode(value):
    if isinstance(value, str):
        try: value = json.loads(value)
        except (ValueError, TypeError): return {}
    return value if isinstance(value, dict) else {}


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values(): yield from walk(child)
    elif isinstance(value, list):
        for child in value: yield from walk(child)


def normalize_content(raw, title, key):
    """Preserve explicit bac_ideas; use factual lesson sections when absent (history)."""
    data = decode(raw)
    ideas = []
    for node in walk(data):
        candidates = node.get('bac_ideas', [])
        if isinstance(candidates, dict): candidates = candidates.get('items', [])
        if isinstance(candidates, list):
            for idea in candidates:
                if isinstance(idea, dict):
                    ideas.append({**idea, 'id': str(idea.get('id') or f'idea-{len(ideas)+1}')})
    # History JSON can use steps, sections or nested story maps. Each textual
    # section is retained as a bounded source; questions must stay within it.
    sections = []
    for node in walk(data):
        if not any(k in node for k in ('title', 'heading')): continue
        facts = {k: v for k, v in node.items() if k not in ('images', 'svg', 'graph_data', 'bac_ideas')}
        serialized = json.dumps(facts, ensure_ascii=False)
        if len(serialized) > 9000 or len(serialized) < 80: continue
        sections.append({'title': node.get('title') or node.get('heading'),
                         'explanation': serialized, 'key_concepts': node.get('key_concepts', []),
                         'common_mistakes': node.get('common_mistakes', []), 'evidences': node.get('evidences', [])})
    original_axes = data.get('axes')
    if isinstance(original_axes, list): sections = [a for a in original_axes if isinstance(a, dict)] or sections
    if not sections and data:
        sections = [{'title': title, 'explanation': json.dumps(data, ensure_ascii=False)[:12000], 'key_concepts': []}]
    if not ideas:
        ideas = [{'id': f'section-{i}', 'title': s['title'], 'prompt': 'اختبر استرجاع المعلومات الواردة في هذا الجزء فقط.',
                  'model_answer': s.get('explanation', '')} for i, s in enumerate(sections, 1)]
    seen = set(); unique = []
    for idea in ideas:
        if idea['id'] not in seen: unique.append(idea); seen.add(idea['id'])
    return {'bac_ideas': unique, 'axes': sections, 'subject_code': key}


def references(axis, branch):
    qs = model('MEMORY_BAC_MODEL', 'exercise_bac.ExerciseBac').objects.filter(is_active=True, chapter_id=axis.chapter_id)
    if branch: qs = qs.filter(Q(branches__code=branch) | Q(branches__isnull=True)).distinct()
    result = []
    for exercise in qs.order_by('-year', 'pk')[:80]:
        tags = exercise.axis_tags or []
        if tags and axis.tag not in tags: continue
        content = decode(exercise.content)
        questions = []
        for q in content.get('questions', []):
            value = q if isinstance(q, str) else (q.get('text') or q.get('question') or q.get('statement') or '') if isinstance(q, dict) else ''
            if isinstance(value, str) and value.strip(): questions.append({'text': value[:700]})
        if questions: result.append({'id': exercise.pk, 'year': exercise.year, 'questions': questions[:8]})
    return result


def snapshot(axis_id, branch='', chapter_id=None):
    axis = get_object_or_404(axes(chapter_id, branch), pk=positive(axis_id, 'المحور'))
    key = subject_key(axis.chapter.subject)
    if key not in ('islamic', 'history'): raise PracticeError('هذا المسار مخصص للإسلامية والتاريخ.', 400)
    content = normalize_content(axis.content, axis.title, key)
    if not content['bac_ideas']: raise PracticeError('محتوى هذا المحور فارغ؛ أضف محتوى الدرس أولًا.', 400)
    lesson, _ = MemoryLesson.objects.update_or_create(tag=f'db-axis-{axis.pk}', defaults={
        'title': axis.title, 'order': axis.order, 'content': content,
        'branches': list(axis.branches.values_list('code', flat=True)),
        'bac_references': [], 'is_active': True})
    # Reference selection is request-local so simultaneous branch requests cannot
    # replace one another's reference examples.
    lesson.bac_references = references(axis, branch)
    return lesson

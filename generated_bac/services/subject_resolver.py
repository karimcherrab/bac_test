from .physics_prompt_builder import UNIT_RULES
from .science_documents import SCIENCE_UNITS


def resolve_subject(content, hint='auto'):
    content=content if isinstance(content,dict) else {}
    unit=content.get('chapter_code','')
    if unit in UNIT_RULES:return 'physics'
    if unit in SCIENCE_UNITS:return 'natural_sciences'
    for value in (content.get('subject_code'),content.get('subject'),hint):
        if value in ('physics','natural_sciences','math'):return value
    return 'math'

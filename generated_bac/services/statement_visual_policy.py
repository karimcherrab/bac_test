"""Decide supplied graphics from the reference, never from a function formula."""
import copy
import re
from .exceptions import AIResponseError

GRAPH_TYPES = {'graph', 'function_graph', 'curve'}
TABLE_TYPES = {'variation_table', 'variations', 'sign_variation_table'}


def prose(content):
    chunks = [str(content.get('statement', ''))]
    for key in ('statement_sections', 'questions'):
        for item in content.get(key, []) or []:
            if isinstance(item, dict): chunks.append(str(item.get('text', '')))
    return re.sub('[\u064b-\u065f\u0640]', '', ' '.join(chunks))


def explicitly_given(text):
    text = re.sub('[\u064b-\u065f\u0640]', '', text)
    return bool(re.search(
        r'(?:المنحنى|التمثيل البياني|الشكل البياني)\s*(?:ال)?(?:المعطى|معطى|المرفق|مرفق|المبين|مبين|الموضح|موضح)'
        r'|(?:المنحنى|التمثيل البياني).{0,35}في\s+(?:الشكل|الرسم)'
        r'|(?:اعتمادا على|بالاعتماد على|انطلاقا من)\s+(?:المنحنى|التمثيل البياني)'
        r'|(?:اقرأ|عين|حدد|استنتج)\s+بيانيا'
        r'|يمثل\s+(?:الشكل|الرسم)\s+(?:المقابل|المرفق|التالي)', text))


def reference_policy(content):
    content = content if isinstance(content, dict) else {}
    graph = bool(content.get('statement_graph_data')) or explicitly_given(prose(content))
    variation = False
    # Only statement-side containers: never recurse into solutions/steps.
    containers = [content] + [q for q in content.get('questions', []) if isinstance(q,dict)] + [s for s in content.get('statement_sections', []) if isinstance(s,dict)]
    for obj in containers:
        for v in (obj.get('visuals', []) or []) + (obj.get('documents', []) or []):
            if not isinstance(v,dict): continue
            kind = str(v.get('type','')).lower()
            graph |= kind in GRAPH_TYPES or bool(v.get('graph'))
            variation |= kind in TABLE_TYPES
    return {'version': 1, 'allow_graph': bool(graph), 'allow_variation_table': bool(variation)}


def apply_policy(data, policy):
    if not isinstance(data,dict): raise AIResponseError('التمرين يجب أن يكون JSON object.')
    data = copy.deepcopy(data)
    def allowed(v):
        if not isinstance(v,dict): return True
        kind = str(v.get('type','')).lower()
        if (kind in GRAPH_TYPES or v.get('graph')) and not policy['allow_graph']: return False
        if kind in TABLE_TYPES and not policy['allow_variation_table']: return False
        return True
    containers = [data] + [q for q in data.get('questions',[]) if isinstance(q,dict)] + [s for s in data.get('statement_sections',[]) if isinstance(s,dict)]
    for obj in containers:
        for key in ('visuals','documents'):
            if isinstance(obj.get(key),list): obj[key] = [v for v in obj[key] if allowed(v)]
        if not policy['allow_graph']: obj.pop('statement_graph_data',None)
    if not policy['allow_graph'] and explicitly_given(prose(data)):
        raise AIResponseError('المرجع لا يعطي منحنى. لا تضف قراءة بيانية ولا عبارة المنحنى المعطى؛ حافظ على الأسئلة التحليلية.')
    if policy['allow_graph']:
        present=bool(data.get('statement_graph_data')) or any(
            isinstance(v,dict) and (v.get('type') in GRAPH_TYPES or v.get('graph'))
            for obj in containers for v in (obj.get('visuals',[]) or [])+(obj.get('documents',[]) or []))
        if not present: raise AIResponseError('المرجع يعطي منحنى: أرجع بيانات منحنى المعطيات نفسه في visuals.')
    data['statement_visual_policy'] = dict(policy)
    return data

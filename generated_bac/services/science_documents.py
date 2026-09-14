"""Reuse existing image assets only. Private metadata is never in student payloads."""
import copy
import re
from urllib.parse import unquote
from .exceptions import AIResponseError

SCIENCE_UNITS={'protein_synthesis','protein_structure_function','enzymatic_catalysis','immune_defense','neural_communication'}


def valid_path(path):
    if not isinstance(path,str) or not path or len(path)>1500:return False
    decoded=unquote(path)
    return not (re.match(r'^[a-z]+:',decoded,re.I) or decoded.startswith('//') or '\\' in decoded or any(x=='..' for x in decoded.split('/')) or any(c in decoded for c in '<>\x00?#')) and decoded.lower().endswith(('.png','.jpg','.jpeg','.webp','.gif'))


def build_catalog(content):
    if not isinstance(content,dict) or content.get('chapter_code') not in SCIENCE_UNITS:
        raise AIResponseError('وحدة العلوم غير معروفة في المرجع.')
    entries=[];seen=set()
    for f in content.get('figures',[]) or []:
        if not isinstance(f,dict):continue
        meta=f.get('metadata') or {}; usage=meta.get('usage_policy') or {}
        key=str(f.get('id',''));path=f.get('path','')
        if not key or key in seen or not valid_path(path):continue
        seen.add(key)
        arabic=meta.get('ai_metadata_ar') or {}
        summary=meta.get('visual_summary') or arabic.get('description_ar') or (f.get('title','') if meta.get('answer_invariants') else '')
        if not isinstance(summary,str) or not summary.strip():continue
        # Explicit permission required. User asked to reuse unchanged, never mutate.
        role='statement' if f.get('usage')=='statement' and usage.get('can_appear_in_generated_statement') is not False and usage.get('generator_eligibility')!='solution_reference_only' else 'solution'
        if role=='solution' and (f.get('usage')!='solution' or usage.get('can_support_solution') is False):continue
        facts=[]
        fields={'observable_elements':meta.get('observable_elements') or arabic.get('visual_elements_ar',[]),
                'answer_invariants':meta.get('answer_invariants',[]),
                'scientific_relationship':meta.get('scientific_relationship') or arabic.get('scientific_interpretation_ar',[]),
                'readable_data':arabic.get('readable_data_ar',[])}
        for evidence in arabic.get('answer_evidence_ar',[]):
            if isinstance(evidence,dict):
                fields.setdefault('answer_evidence',[]).append(' / '.join(str(evidence[k]) for k in ('observation','supports') if evidence.get(k)))
        for field,values in fields.items():
            if isinstance(values,str):values=[values]
            if isinstance(values,list):
                for value in values:
                    if isinstance(value,str) and value.strip():
                        facts.append({'id':f'{key}:e{len(facts)+1}','kind':field,'text':value})
        if not facts:continue
        entries.append({'id':key,'path':path,'title':str(f.get('title',key)), 'role':role,
            'summary':summary,'facts':facts,'operations':meta.get('question_operations') or arabic.get('recommended_question_patterns_ar',[]),
            'forbidden_changes':(meta.get('forbidden_changes',[]) or [])+(arabic.get('ai_generation_guidance_ar',[]) or []),
            'linked_question_ids':meta.get('linked_question_ids',[]),
            'can_support_solution':usage.get('can_support_solution') is not False})
    statements=[d for d in entries if d['role']=='statement'][:3]
    if not statements:raise AIResponseError('هذا المرجع لا يحتوي وثيقة معطيات لها صورة ووصف علمي صالحان.')
    # Keep a bounded, coherent set from one source. Solution images stay private until requested.
    selected_ids={x for d in statements for x in d['linked_question_ids']}
    corrections=[d for d in entries if d['role']=='solution' and selected_ids.intersection(d['linked_question_ids'])][:2]
    for d in corrections:
        d['linked_document_ids']=[s['id'] for s in statements if set(s['linked_question_ids']).intersection(d['linked_question_ids'])]
    return statements+corrections


def public_document(doc):
    return {'reuse_unchanged':True,'ref_id':doc['id'],'id':doc['id'],'type':'image','title':doc['title'],'path':doc['path']}


def prompt_catalog(catalog, solution=False):
    return [{k:v for k,v in d.items() if k not in ('path','linked_question_ids')} for d in catalog if solution or d['role']=='statement']


def refs(value, available, name, nonempty=True):
    if not isinstance(value,list) or any(not isinstance(x,str) for x in value) or (nonempty and not value):
        raise AIResponseError(name+' يجب أن تكون قائمة معرفات غير فارغة.')
    if len(value)!=len(set(value)) or not set(value)<=set(available):raise AIResponseError(name+' يحتوي معرفًا غير موجود أو مكررًا.')
    return value


def string(value,name):
    if not isinstance(value,str) or not value.strip():raise AIResponseError(name+' يجب أن يكون نصًا غير فارغ.')
    # Paths/markup cannot be smuggled into prose; UI renders only catalog assets.
    if re.search(r'<\s*(?:svg|img|iframe|script)|!\[|https?://|data:image|(?:/public/|\.(?:png|jpe?g|webp)\b)',value,re.I):
        raise AIResponseError('لا تضع صورًا أو روابط في النص؛ استعمل document_refs فقط.')
    return value.strip()


def validate_exercise(data,catalog):
    if not isinstance(data,dict):raise AIResponseError('تمرين العلوم غير صالح.')
    allowed={d['id']:d for d in catalog if d['role']=='statement'}
    questions=data.get('questions')
    if not isinstance(questions,list) or not 2<=len(questions)<=10:raise AIResponseError('أرسل بين سؤالين و10 أسئلة مترابطة.')
    cleaned=[];used=[];ids=set()
    for i,q in enumerate(questions,1):
        if not isinstance(q,dict):raise AIResponseError('السؤال غير صالح.')
        qid=string(q.get('id'), 'id')
        if qid in ids:raise AIResponseError('معرف سؤال مكرر.')
        ids.add(qid)
        doc_ids=refs(q.get('document_refs'),allowed,'document_refs')
        for key in doc_ids:
            if key not in used:used.append(key)
        question=string(q.get('text'),'السؤال')
        if re.search(r'ارسم|أرسم|أنجز.*(?:منحنى|رسم)|انجز.*(?:منحنى|رسم)|أكمل.*الرسم',question):
            raise AIResponseError('استبدل طلب رسم جديد بسؤال تحليل أو تفسير للوثيقة الموجودة.')
        evidence={f['id'] for key in doc_ids for f in allowed[key]['facts']}
        # Evidence plans are checked but not exposed to the student before solving.
        refs(q.get('evidence_refs'),evidence,'evidence_refs')
        cleaned.append({'id':qid,'display_order':i,'text':question,'skill':str(q.get('skill','تحليل وثيقة')),
                        'points':1,'document_refs':doc_ids,'visuals':[]})
    return {'title':string(data.get('title'),'العنوان'),'statement':string(data.get('statement'),'السياق'),
        'subject_code':'natural_sciences','statement_sections':[], 'visuals':[],
        'documents':[public_document(allowed[key]) for key in used],
        'questions':cleaned,'estimated_points':len(cleaned),
        'statement_visual_policy':{'version':3,'subject':'natural_sciences','allow_graph':False,'allow_variation_table':False}}


def validate_solution(data, *, catalog, exercise, exercise_id):
    if not isinstance(data,dict):raise AIResponseError('حل العلوم غير صالح.')
    questions=data.get('questions',[]);expected=exercise.get('questions',[])
    if not isinstance(questions,list) or len(questions)!=len(expected):raise AIResponseError('الحل يجب أن يجيب عن كل الأسئلة.')
    by_id={d['id']:d for d in catalog};out=[]
    for q,original in zip(questions,expected):
        if not isinstance(q,dict) or q.get('question_id')!=original['id']:raise AIResponseError('معرفات الحل لا تطابق الأسئلة.')
        selected=set(original['document_refs'])
        allowed={key:d for key,d in by_id.items() if (key in selected and d['can_support_solution']) or (d['role']=='solution' and d['can_support_solution'] and selected.intersection(d.get('linked_document_ids',[])))}
        evidence={f['id'] for key in selected for f in by_id[key]['facts']}
        steps=q.get('steps',[])
        if not isinstance(steps,list) or not 1<=len(steps)<=10:raise AIResponseError('أرسل خطوات حل واضحة.')
        result=[]
        for n,step in enumerate(steps,1):
            if not isinstance(step,dict):raise AIResponseError('خطوة حل غير صالحة.')
            ev=refs(step.get('evidence_refs'),evidence,'evidence_refs')
            result.append({'step_number':n,'title':str(step.get('title','')),
                'explanation':string(step.get('explanation'),'الشرح'),'latex':str(step.get('latex','')),
                'visuals':[],'evidence_refs':ev})
        doc_ids=refs(q.get('document_refs',[]),allowed,'document_refs',False)
        out.append({'question_id':original['id'],'question_text':original['text'], 'strategy':str(q.get('strategy','')),
            'steps':result,'final_answer':string(q.get('final_answer'),'الجواب النهائي'),'visuals':[],
            'documents':[public_document(allowed[key]) for key in doc_ids],
            'verification':str(q.get('verification','')),'hints':[],'common_mistakes':[],'bac_writing':[]})
    return {'exercise_id':exercise_id,'general_strategy':str(data.get('general_strategy','')),'questions':out}


def validate_reexplanation(data, *, catalog, question):
    candidate={'questions':[dict(data,question_id=question['id'])]}
    result=validate_solution(candidate,catalog=catalog,exercise={'questions':[question]},exercise_id=0)['questions'][0]
    return dict(result,title='شرح مبسط',simple_idea=str(data.get('simple_idea','')))

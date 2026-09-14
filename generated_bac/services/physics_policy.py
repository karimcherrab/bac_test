import re
from .exceptions import AIResponseError
from .physics_prompt_builder import UNIT_RULES
from .statement_visual_policy import explicitly_given


def unit_code(reference):
    code=(reference.content or {}).get('chapter_code','')
    if code not in UNIT_RULES:
        raise AIResponseError('الوحدة الفيزيائية غير معروفة في المرجع؛ تحقق من chapter_code في content.')
    return code


def physics_policy(content):
    # Existing reference figures use statement_graphs, figures, graph_data and sections.
    figures=[]
    for key in ('figures','statement_graphs','statement_graph_data','documents','visuals'):
        value=content.get(key)
        if isinstance(value,list):figures.extend(value)
        elif isinstance(value,dict) and value:figures.append(value)
    sections=content.get('statement_sections',[]) or []
    for sec in sections:
        if isinstance(sec,dict):
            for key in ('visuals','documents'):
                if isinstance(sec.get(key),list):figures.extend(sec[key])
    descriptions=' '.join(str(v.get('title',''))+' '+str(v.get('description',''))+' '+str(v.get('type',''))+' '+str(v.get('diagram_type','')) for v in figures if isinstance(v,dict))
    statement=str(content.get('statement',''))
    circuit=bool(re.search(r'دارة|داره|circuit|نربط.{0,30}(?:التسلسل|التفرع)',statement+' '+descriptions,re.I))
    graph=bool(re.search(r'منحن|بيان|graph|curve',descriptions,re.I)) or any(isinstance(v,dict) and (v.get('series') or v.get('expression') or v.get('graph')) for v in figures)
    # A question requiring reading from an already supplied graph is also evidence.
    texts=statement+' '+' '.join(str(q.get('text','')) for q in content.get('questions',[]) if isinstance(q,dict))
    graph |= explicitly_given(texts)
    supplied_forces=bool(re.search(r'مخطط القوى|تمثيل القوى|forces', descriptions, re.I))
    return {'allow_forces':supplied_forces, 'version':2,'subject':'physics','allow_graph':bool(graph),'allow_variation_table':False,'needs_circuit':circuit}


def question_requirements(q):
    t=re.sub('[\u064b-\u065f\u0640]','',str(q.get('text','')))
    raw=q.get('required_visuals',[]) or []
    if not isinstance(raw,list) or any(not isinstance(x,str) for x in raw):raise AIResponseError('required_visuals يجب أن تكون قائمة أنواع.')
    required=set(raw)
    if re.search(r'(?:مثل|ارسم|وضح).{0,40}(?:القوى|القوة)',t):required.add('forces')
    if re.search(r'(?:ارسم|انشئ|أرسم|أكمل|اكمل).{0,35}(?:الدارة|دارة|دارة كهربائية)',t):required.add('circuit')
    if re.search(r'(?:ارسم|مثل|أنشئ|انشئ).{0,30}(?:المنحنى|منحنى|بيانيا)',t):required.add('physics_graph')
    if re.search(r'(?:أنشئ|انشئ|أكمل|اكمل|شكل).{0,20}جدول',t):required.add('table')
    if not required <= {'forces','circuit','physics_graph','table','diagram'}:raise AIResponseError('نوع الرسم المطلوب غير مدعوم.')
    return sorted(required)


def validate_physics_exercise(data, policy):
    from .validators import ExerciseValidator
    if not isinstance(data,dict):raise AIResponseError('التمرين غير صالح.')
    for q in data.get('questions',[]):
        if isinstance(q,dict):
            q['required_visuals']=question_requirements(q)
    data['statement_visual_policy']=policy
    # No inference/synthetic graph in the UI; preserve explicit supplied figures only.
    if not policy['allow_graph']:
        containers=[data]+[q for q in data.get('questions',[]) if isinstance(q,dict)]
        for obj in containers:
            if isinstance(obj.get('visuals'),list):obj['visuals']=[v for v in obj['visuals'] if not isinstance(v,dict) or v.get('type') not in ('graph','physics_graph')]
    for obj in [data]+[q for q in data.get('questions',[]) if isinstance(q,dict)]:
        if not policy.get('allow_forces',False) and isinstance(obj.get('visuals'),list):
            obj['visuals']=[v for v in obj['visuals'] if not isinstance(v,dict) or v.get('type')!='forces']
    if not policy['allow_graph'] and explicitly_given(str(data.get('statement',''))):
        raise AIResponseError('لا تشر إلى منحنى معطى غير موجود في المرجع.')
    kinds={v.get('type') for v in data.get('visuals',[]) if isinstance(v,dict)}
    if policy['needs_circuit'] and 'circuit' not in kinds:raise AIResponseError('أضف الدارة المعطاة إلى visuals في نص التمرين.')
    if policy['allow_graph'] and 'physics_graph' not in kinds:raise AIResponseError('أضف المنحنى الفيزيائي المعطى إلى visuals مع الوحدات الصحيحة.')
    data['subject_code']='physics'
    return ExerciseValidator().validate(data)

import json,os
from django.conf import settings
from groq import Groq

class PracticeError(Exception):
    def __init__(self,message,status=422):super().__init__(message);self.status=status

def ask(system,payload,max_tokens=2200):
    key=os.getenv('GROQ_API_KEY') or os.getenv('API_KEY') or getattr(settings,'GROQ_API_KEY','')
    if not key:raise PracticeError('مفتاح Groq غير مضبوط في الخادم.',503)
    client=Groq(api_key=key,timeout=70,max_retries=0)
    prompt=json.dumps(payload,ensure_ascii=False)
    for attempt in range(2):
        try:
            model=os.getenv('GROQ_MEMORY_MODEL') or os.getenv('GROQ_MODEL','openai/gpt-oss-120b')
            options={'reasoning_effort':'low'} if model.startswith('openai/gpt-oss-') else {}
            reply=client.chat.completions.create(model=model,messages=[{'role':'system','content':system},{'role':'user','content':prompt}],response_format={'type':'json_object'},max_completion_tokens=max_tokens,temperature=0.15,**options)
            choice=reply.choices[0]
            if choice.finish_reason=='length':raise ValueError('length')
            value=json.loads(choice.message.content or '')
            if not isinstance(value,dict):raise ValueError('object')
            return value
        except Exception as exc:
            code=getattr(exc,'status_code',None)
            if code==429:raise PracticeError('المصحح مشغول مؤقتًا. إجابتك باقية؛ حاول بعد قليل.',429) from exc
            if isinstance(exc,(ValueError,json.JSONDecodeError)) or (code==400 and 'json_validate_failed' in str(exc)):
                if not attempt:
                    prompt+='\nأعد JSON مكتملًا بإجابة أقصر دون حذف معايير التصحيح.';continue
            raise PracticeError('تعذر إكمال الطلب الآن. احتفظ بإجابتك وأعد المحاولة.',503) from exc

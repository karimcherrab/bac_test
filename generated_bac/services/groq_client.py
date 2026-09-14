import json
import logging
import os
from groq import Groq
from django.conf import settings
from .exceptions import AIResponseError, AIRateLimitError

logger = logging.getLogger(__name__)


class GroqJSONClient:
    def __init__(self, model=None):
        key = os.getenv('GROQ_API_KEY') or os.getenv('API_KEY') or getattr(settings, 'GROQ_API_KEY', '')
        if not key:
            raise AIResponseError('أضف GROQ_API_KEY إلى إعدادات الخادم.')
        self.model = model or os.getenv('GROQ_EXERCISE_MODEL') or os.getenv('GROQ_MODEL') or 'openai/gpt-oss-120b'
        self.client = Groq(api_key=key, timeout=90, max_retries=0)

    def generate_json(self, *, system_prompt, user_prompt, temperature=0.2, max_tokens=4200):
        # Estimate only: real provider TPM accounting depends on model/tokenizer/tier.
        budget = int(os.getenv('GROQ_REQUEST_TOKEN_BUDGET', '8000'))
        estimated_input = (len(system_prompt)+len(user_prompt))//2
        output = min(max_tokens, budget-estimated_input-200)
        if output < 1800:
            raise AIResponseError('التمرين المرجعي كبير لهذا الحد من Groq. اختر مرجعًا أقصر أو ارفع GROQ_REQUEST_TOKEN_BUDGET بما يناسب حسابك.')
        for attempt in range(2):
            try:
                response = self.client.chat.completions.create(
                    model=self.model, messages=[{'role':'system','content':system_prompt},
                    {'role':'user','content':user_prompt}], temperature=temperature,
                    max_completion_tokens=output, response_format={'type':'json_object'})
                choice=response.choices[0]
                if choice.finish_reason == 'length':
                    if attempt == 0:
                        user_prompt += '\nالمحاولة السابقة تجاوزت الحجم: أعد إجابة مكتملة أقصر، 2 إلى 4 خطوات دون تكرار، مع الحفاظ على الرسم والنتيجة. لا تكمل JSON المقطوع.'
                        continue
                    raise AIResponseError('تعذر إكمال هذا الجزء ضمن الحجم المتاح. الأجزاء السابقة محفوظة؛ اضغط استكمال الحل للمحاولة مجددًا.')
                value=json.loads(choice.message.content or '')
                if not isinstance(value,dict): raise ValueError('not an object')
                return value, self.model
            except AIResponseError:
                raise
            except Exception as exc:
                code=getattr(exc,'status_code',None)
                logger.warning('Groq failure: type=%s status=%s',type(exc).__name__,code)
                if code == 429:
                    raise AIRateLimitError('بلغ حساب Groq حد الطلبات مؤقتًا. التقدم محفوظ؛ انتظر ثم استكمل الحل.') from exc
                if code == 413:
                    raise AIResponseError('وصل حساب Groq إلى حد الطلبات أو الرموز. انتظر قليلًا ثم أعد المحاولة.') from exc
                if code in (401,403):
                    raise AIResponseError('تحقق من مفتاح Groq وصلاحية النموذج في حسابك.') from exc
                malformed=isinstance(exc,(json.JSONDecodeError,ValueError)) or (code==400 and 'json_validate_failed' in str(exc))
                if malformed and attempt==0:
                    user_prompt += '\nأرجع JSON كاملًا صالحًا فقط، واختصر الشرح دون حذف أي سؤال.'
                    continue
                raise AIResponseError('تعذر توليد المحتوى من Groq حاليًا. تحقق من اتصال الخادم والنموذج ثم أعد المحاولة.') from exc

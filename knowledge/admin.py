from django.contrib import admin
#
# # Register your models here.
# import json
# import re
# from typing import Any
#
# from knowledge.models import KnowledgeItem
# from knowledge.retrieval.answer_generator import AnswerGenerator
# from knowledge.retrieval.context_builder import BuiltContext
#
#
# class ExplainCourService:
#     """
#     خدمة توليد شرح مبسط وتفاعلي لدرس رياضيات.
#
#     تعالج:
#     - JSON المحاط بـ Markdown.
#     - أوامر LaTeX ذات الشرطة العكسية غير المحمية داخل JSON.
#     - بعض إجابات JSON المقطوعة في آخر النص.
#     - تنظيف LaTeX داخل جميع المراحل والحقول المتداخلة.
#     """
#
#     MAX_LESSON_CONTENT_LENGTH = 10_000
#     MAX_LEARNING_STEPS = 9
#     MAX_REPAIR_RAW_LENGTH = 12_000
#
#     LATEX_COMMANDS = (
#         "frac", "dfrac", "tfrac", "sqrt", "mathbb", "mathbf", "mathrm",
#         "text", "operatorname", "left", "right", "begin", "end", "cdot",
#         "times", "div", "pm", "mp", "le", "leq", "ge", "geq", "neq",
#         "approx", "sim", "equiv", "infty", "to", "mapsto", "lim", "sum",
#         "prod", "int", "ln", "log", "exp", "sin", "cos", "tan", "arctan",
#         "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon",
#         "lambda", "mu", "pi", "theta", "ell", "forall", "exists", "in",
#         "notin", "subset", "subseteq", "supset", "supseteq", "cup", "cap",
#         "overline", "underline", "vec", "overrightarrow", "overleftarrow",
#         "geqslant", "leqslant", "quad", "qquad"
#     )
#
#     STANDALONE_MATH_KEYS = {
#         "calculation",
#         "calculation_template",
#         "conclusion_template",
#         "math",
#         "formula",
#         "final_math",
#         "question_latex",
#     }
#
#     def __init__(self):
#         self.generator = AnswerGenerator()
#
#     # =========================================================
#     # JSON EXTRACTION
#     # =========================================================
#
#     def clean_model_response(self, value: Any) -> str:
#         if value is None:
#             return ""
#
#         text = str(value).strip()
#
#         text = re.sub(
#             r"^\s*```(?:json)?\s*",
#             "",
#             text,
#             flags=re.IGNORECASE,
#         )
#         text = re.sub(
#             r"\s*```\s*$",
#             "",
#             text,
#             flags=re.IGNORECASE,
#         )
#
#         return text.strip()
#
#     def protect_latex_backslashes_in_json(self, text: str) -> str:
#         """
#         يحمي أوامر LaTeX داخل JSON قبل json.loads.
#
#         مثال:
#             \frac{1}{n}
#
#         يصبح داخل JSON:
#             \\frac{1}{n}
#         """
#         if not text:
#             return ""
#
#         commands = "|".join(
#             sorted(
#                 map(re.escape, self.LATEX_COMMANDS),
#                 key=len,
#                 reverse=True,
#             )
#         )
#
#         text = re.sub(
#             rf"(?<!\\)\\(?=(?:{commands})\b)",
#             r"\\\\",
#             text,
#         )
#
#         # حماية محددات LaTeX: \( \) \[ \]
#         text = re.sub(
#             r"(?<!\\)\\(?=[()\[\]])",
#             r"\\\\",
#             text,
#         )
#
#         return text
#
#     def extract_first_json_object(self, text: str) -> str:
#         """
#         يستخرج أول كائن JSON متوازن مع احترام النصوص وعلامات الهروب.
#         """
#         if not text:
#             return ""
#
#         start = text.find("{")
#         if start == -1:
#             return ""
#
#         depth = 0
#         in_string = False
#         escaped = False
#
#         for index in range(start, len(text)):
#             char = text[index]
#
#             if in_string:
#                 if escaped:
#                     escaped = False
#                 elif char == "\\":
#                     escaped = True
#                 elif char == '"':
#                     in_string = False
#                 continue
#
#             if char == '"':
#                 in_string = True
#             elif char == "{":
#                 depth += 1
#             elif char == "}":
#                 depth -= 1
#                 if depth == 0:
#                     return text[start:index + 1]
#
#         return text[start:]
#
#     def remove_dangling_json_tail(self, text: str) -> str:
#         """
#         يحذف ذيلاً غير مكتمل مثل:
#         ,"key":
#         أو فاصلة نهائية قبل إغلاق JSON.
#         """
#         if not text:
#             return ""
#
#         text = text.rstrip()
#
#         # حذف فاصلة أو نقطتين معلقتين في النهاية.
#         text = re.sub(r",\s*$", "", text)
#         text = re.sub(r":\s*$", ": null", text)
#
#         # حذف مفتاح JSON غير مكتمل في آخر النص.
#         text = re.sub(
#             r',\s*"[^"]*"\s*:\s*"[^"]*$',
#             "",
#             text,
#             flags=re.DOTALL,
#         )
#         text = re.sub(
#             r',\s*"[^"]*"\s*:\s*$',
#             "",
#             text,
#             flags=re.DOTALL,
#         )
#         text = re.sub(
#             r',\s*"[^"]*$',
#             "",
#             text,
#             flags=re.DOTALL,
#         )
#
#         return text.rstrip()
#
#     def close_truncated_json(self, candidate: str) -> str:
#         """
#         محاولة محافظة لإغلاق JSON المقطوع.
#
#         لا تعيد كتابة المحتوى؛ فقط:
#         - تغلق النص المفتوح.
#         - تغلق الأقواس المربعة والمعقوفة الناقصة.
#         - تحذف الفاصلة الأخيرة.
#         """
#         if not candidate:
#             return ""
#
#         candidate = self.remove_dangling_json_tail(candidate)
#
#         stack = []
#         in_string = False
#         escaped = False
#
#         for char in candidate:
#             if in_string:
#                 if escaped:
#                     escaped = False
#                 elif char == "\\":
#                     escaped = True
#                 elif char == '"':
#                     in_string = False
#                 continue
#
#             if char == '"':
#                 in_string = True
#             elif char == "{":
#                 stack.append("}")
#             elif char == "[":
#                 stack.append("]")
#             elif char in ("}", "]"):
#                 if stack and stack[-1] == char:
#                     stack.pop()
#
#         if in_string:
#             candidate += '"'
#
#         candidate = re.sub(r",\s*$", "", candidate.rstrip())
#
#         while stack:
#             candidate += stack.pop()
#
#         return candidate
#
#     def parse_json_candidate(self, candidate: str) -> dict:
#         if not candidate:
#             return {}
#
#         attempts = [
#             candidate,
#             self.protect_latex_backslashes_in_json(candidate),
#         ]
#
#         repaired = self.close_truncated_json(candidate)
#         if repaired and repaired != candidate:
#             attempts.extend([
#                 repaired,
#                 self.protect_latex_backslashes_in_json(repaired),
#             ])
#
#         seen = set()
#
#         for attempt in attempts:
#             if not attempt or attempt in seen:
#                 continue
#
#             seen.add(attempt)
#
#             try:
#                 parsed = json.loads(attempt)
#                 if isinstance(parsed, dict):
#                     return parsed
#             except (json.JSONDecodeError, TypeError, ValueError):
#                 continue
#
#         return {}
#
#     def extract_json(self, value: Any) -> dict:
#         if isinstance(value, dict):
#             return value
#
#         text = self.clean_model_response(value)
#
#         if not text:
#             return {}
#
#         parsed = self.parse_json_candidate(text)
#         if parsed:
#             return parsed
#
#         candidate = self.extract_first_json_object(text)
#         parsed = self.parse_json_candidate(candidate)
#
#         if parsed:
#             return parsed
#
#         return {"raw_answer": text}
#
#     # =========================================================
#     # LATEX CLEANING
#     # =========================================================
#
#     def restore_json_control_characters(self, text: str) -> str:
#         if not text:
#             return ""
#
#         repairs = {
#             "\x0crac": r"\frac",
#             "\x0cdfrac": r"\dfrac",
#             "\x0ctfrac": r"\tfrac",
#             "\x08egin": r"\begin",
#             "\x08eta": r"\beta",
#             "\t" + "o": r"\to",
#             "\t" + "imes": r"\times",
#             "\r" + "ight": r"\right",
#             "\n" + "eq": r"\neq",
#             "\n" + "otin": r"\notin",
#         }
#
#         for old, new in repairs.items():
#             text = text.replace(old, new)
#
#         return text
#
#     def repair_latex_commands(self, text: str) -> str:
#         if not text:
#             return ""
#
#         commands_with_brace = (
#             "frac", "dfrac", "tfrac", "sqrt", "mathbb", "mathbf",
#             "mathrm", "text", "operatorname", "begin", "end",
#             "overline", "underline", "vec", "overrightarrow",
#             "overleftarrow",
#         )
#
#         for command in commands_with_brace:
#             text = re.sub(
#                 rf"(?<![\\A-Za-z]){command}\s*\{{",
#                 rf"\\{command}{{",
#                 text,
#             )
#
#         simple_commands = (
#             "left", "right", "cdot", "times", "div", "pm", "mp", "le",
#             "leq", "ge", "geq", "neq", "approx", "sim", "equiv",
#             "infty", "to", "mapsto", "lim", "sum", "prod", "int", "ln",
#             "log", "exp", "sin", "cos", "tan", "arctan", "alpha", "beta",
#             "gamma", "delta", "epsilon", "varepsilon", "lambda", "mu",
#             "pi", "theta", "ell", "forall", "exists", "notin", "subset",
#             "subseteq", "supset", "supseteq", "cup", "cap", "geqslant",
#             "leqslant", "quad", "qquad",
#         )
#
#         for command in simple_commands:
#             text = re.sub(
#                 rf"(?<![\\A-Za-z]){command}\b",
#                 rf"\\{command}",
#                 text,
#             )
#
#         text = re.sub(
#             r"\\(?:d?frac|tfrac)\s*([A-Za-z0-9])\s*([A-Za-z0-9])",
#             lambda match: (
#                 rf"\frac{{{match.group(1)}}}{{{match.group(2)}}}"
#             ),
#             text,
#         )
#
#         return text
#
#     def balance_latex_braces(self, text: str) -> str:
#         if not text:
#             return ""
#
#         balance = 0
#         escaped = False
#
#         for char in text:
#             if escaped:
#                 escaped = False
#                 continue
#
#             if char == "\\":
#                 escaped = True
#             elif char == "{":
#                 balance += 1
#             elif char == "}" and balance > 0:
#                 balance -= 1
#
#         if balance > 0:
#             text += "}" * balance
#
#         return text
#
#     def normalize_latex_source(self, value: Any) -> str:
#         if value is None:
#             return ""
#
#         text = str(value)
#         text = self.restore_json_control_characters(text)
#
#         replacements = {
#             "\u200b": "",
#             "\u200c": "",
#             "\u200d": "",
#             "\ufeff": "",
#             "```json": "",
#             "```latex": "",
#             "```math": "",
#             "```": "",
#             "∞": r"\infty",
#             "→": r"\to",
#             "×": r"\times",
#             "÷": r"\div",
#             "≤": r"\leq",
#             "≥": r"\geq",
#             "≠": r"\neq",
#             "≈": r"\approx",
#         }
#
#         for old, new in replacements.items():
#             text = text.replace(old, new)
#
#         text = self.repair_latex_commands(text)
#         text = self.balance_latex_braces(text)
#
#         return text
#
#     def add_spaces_around_inline_math(self, text: str) -> str:
#         if not text:
#             return ""
#
#         text = re.sub(r"\s*\\\(", r" \\(", text)
#         text = re.sub(r"\\\)\s*", r"\\) ", text)
#         text = re.sub(r"[ \t]{2,}", " ", text)
#
#         return text.strip()
#
#     def clean_text(self, value: Any) -> str:
#         """
#         تنظيف النص العربي مع المحافظة على LaTeX المضمن.
#         """
#         if value is None:
#             return ""
#
#         text = self.normalize_latex_source(value)
#
#         if not text:
#             return ""
#
#         text = text.replace("\r\n", "\n").replace("\r", "\n")
#         text = text.replace("$$", "")
#
#         text = re.sub(
#             r"(?<!\\)\$(.+?)(?<!\\)\$",
#             r"\\(\1\\)",
#             text,
#             flags=re.DOTALL,
#         )
#
#         text = re.sub(r"^\s*#{1,6}\s*", "", text)
#
#         def fix_inline(match: re.Match) -> str:
#             content = self.normalize_latex_source(
#                 match.group(1)
#             ).strip()
#
#             content = self.balance_latex_braces(content)
#
#             return rf"\({content}\)" if content else ""
#
#         text = re.sub(
#             r"\\\((.*?)\\\)",
#             fix_inline,
#             text,
#             flags=re.DOTALL,
#         )
#
#         text = self.add_spaces_around_inline_math(text)
#         text = re.sub(r"[ \t]{2,}", " ", text)
#         text = re.sub(r"\n{3,}", "\n\n", text)
#
#         return text.strip()
#
#     def clean_latex(self, value: Any, display: bool = False) -> str:
#         """
#         تنظيف حقل يحتوي LaTeX فقط.
#
#         display=False يعيد:
#             \( ... \)
#
#         display=True يعيد:
#             \[ ... \]
#         """
#         latex_value = self.normalize_latex_source(value)
#
#         if not latex_value:
#             return ""
#
#         latex_value = latex_value.replace("$$", "")
#         latex_value = latex_value.replace("$", "")
#
#         latex_value = re.sub(
#             r"^\s*\\\[\s*|\s*\\\]\s*$",
#             "",
#             latex_value,
#         )
#         latex_value = re.sub(
#             r"^\s*\\\(\s*|\s*\\\)\s*$",
#             "",
#             latex_value,
#         )
#
#         latex_value = self.repair_latex_commands(latex_value)
#         latex_value = self.balance_latex_braces(latex_value)
#         latex_value = re.sub(
#             r"[ \t]{2,}",
#             " ",
#             latex_value,
#         ).strip()
#
#         if not latex_value:
#             return ""
#
#         return (
#             rf"\[{latex_value}\]"
#             if display
#             else rf"\({latex_value}\)"
#         )
#
#     # =========================================================
#     # NORMALIZATION
#     # =========================================================
#
#     def normalize_text(self, value: Any, default: str = "") -> str:
#         cleaned = self.clean_text(value)
#         return cleaned if cleaned else default
#
#     def ensure_list(self, value: Any) -> list:
#         if isinstance(value, list):
#             return value
#
#         if value in (None, ""):
#             return []
#
#         return [value]
#
#     def normalize_nested_value(
#         self,
#         value: Any,
#         key: str = "",
#     ) -> Any:
#         """
#         ينظف كل الحقول المتداخلة دون الحاجة لكتابة Normalizer
#         منفصل لكل نوع Card.
#         """
#         if isinstance(value, dict):
#             normalized = {}
#
#             for child_key, child_value in value.items():
#                 normalized[child_key] = self.normalize_nested_value(
#                     child_value,
#                     key=child_key,
#                 )
#
#             return normalized
#
#         if isinstance(value, list):
#             return [
#                 self.normalize_nested_value(item, key=key)
#                 for item in value
#             ]
#
#         if isinstance(value, str):
#             if key in self.STANDALONE_MATH_KEYS:
#                 return self.clean_latex(
#                     value,
#                     display=False,
#                 )
#
#             return self.clean_text(value)
#
#         return value
#
#     def normalize_learning_path(self, value: Any) -> list[dict]:
#         normalized_steps = []
#
#         for index, step in enumerate(
#             self.ensure_list(value)[:self.MAX_LEARNING_STEPS],
#             start=1,
#         ):
#             if not isinstance(step, dict):
#                 continue
#
#             normalized_step = self.normalize_nested_value(step)
#
#             normalized_step["id"] = self.normalize_text(
#                 normalized_step.get("id"),
#                 f"step_{index}",
#             )
#
#             normalized_step["type"] = self.normalize_text(
#                 normalized_step.get("type"),
#                 "guided_explanation",
#             )
#
#             normalized_step["title"] = self.normalize_text(
#                 normalized_step.get("title"),
#                 f"المرحلة {index}",
#             )
#
#             normalized_steps.append(normalized_step)
#
#         return normalized_steps
#
#     def normalize_answer(self, answer: Any) -> dict:
#         if not isinstance(answer, dict):
#             answer = {}
#
#         return {
#             "title": self.normalize_text(
#                 answer.get("title"),
#                 "شرح الدرس",
#             ),
#             "lesson_goal": self.normalize_text(
#                 answer.get("lesson_goal"),
#             ),
#             "estimated_duration": self.normalize_text(
#                 answer.get("estimated_duration"),
#                 "15 دقيقة",
#             ),
#             "learning_path": self.normalize_learning_path(
#                 answer.get("learning_path")
#             ),
#         }
#
#     # =========================================================
#     # PROMPTS
#     # =========================================================
#
#     def limit_lesson_content(self, content: Any) -> str:
#         content = self.normalize_text(content)
#
#         if len(content) <= self.MAX_LESSON_CONTENT_LENGTH:
#             return content
#
#         return (
#             content[:self.MAX_LESSON_CONTENT_LENGTH]
#             + "\n\n[تم اختصار بقية المحتوى لتقليل حجم الطلب.]"
#         )
#
#     def build_prompt(
#         self,
#         axis_title: str,
#         lesson_title: str,
#         lesson_content: str,
#     ) -> str:
#         lesson_data = {
#             "axis_title": axis_title,
#             "lesson_title": lesson_title,
#             "lesson_content": lesson_content,
#         }
#
#         lesson_json = json.dumps(
#             lesson_data,
#             ensure_ascii=False,
#             indent=2,
#         )
#
#         prompt_template = r"""
# أنت أستاذ رياضيات جزائري خبير في تدريس تلاميذ السنة الثالثة ثانوي
# والتحضير لشهادة البكالوريا.
#
# اشرح الدرس تدريجياً كما يشرح أستاذ داخل القسم.
# اجعل الشرح واضحاً، قصيراً، تفاعلياً، وغير ممل.
#
# ==================================================
# قواعد الإخراج
# ==================================================
#
# 1. أرجع كائن JSON صالحاً فقط.
# 2. لا تكتب أي شيء قبل JSON أو بعده.
# 3. لا تستعمل Markdown أو code fences.
# 4. استعمل علامات الاقتباس المزدوجة.
# 5. لا تضع فاصلة بعد آخر عنصر.
# 6. لا تضف حقولاً خارج البنية المطلوبة.
# 7. أنشئ من 6 إلى 8 مراحل فقط حتى لا ينقطع الجواب.
# 8. اجعل كل حقل نصي قصيراً.
# 9. لا تجعل أي فقرة تتجاوز 300 حرف تقريباً.
# 10. ضع سؤالاً واحداً فقط في mini_quiz.
# 11. ضع خطأين شائعين كحد أقصى.
# 12. ضع ثلاث خطوات كحد أقصى في worked_example.
# 13. لا تكرر التعريف أو القانون نفسه.
#
# ==================================================
# قواعد LaTeX وJSON
# ==================================================
#
# 1. أي تعبير رياضي داخل نص عربي يوضع بين \( و \).
#
# مثال:
# تقترب المتتالية \(u_n=\frac{1}{n}\) من الصفر.
#
# 2. اترك مسافة قبل وبعد كل تعبير رياضي.
#
# 3. داخل JSON يجب مضاعفة الشرطة العكسية.
#
# صحيح:
# "content": "لدينا \(u_n=\\frac{1}{n}\)."
#
# 4. لا تستعمل:
# $ ... $
# $$ ... $$
# \[ ... \]
# \displaystyle
# \Large
# \Huge
#
# 5. اكتب الكسور هكذا:
# \frac{a}{b}
#
# 6. اكتب الفهارس والأسس هكذا:
# u_{n+1}
# x^{2}
#
# 7. لا تضع جملة عربية كاملة داخل LaTeX.
#
# ==================================================
# طريقة الشرح
# ==================================================
#
# - ابدأ بمثال بسيط.
# - اجعل التلميذ يلاحظ قبل إعطاء القاعدة.
# - اتبع:
#   نلاحظ ← نفكر ← نحسب ← نستنتج.
# - اشرح سبب كل خطوة.
# - بعد الفكرة المهمة ضع سؤال تحقق قصيراً.
# - اختر مثالاً تطبيقياً واضحاً.
# - لا تملأ الحقول بحشو غير مفيد.
#
# ==================================================
# بنية JSON المطلوبة
# ==================================================
#
# {
#   "title": "",
#   "lesson_goal": "",
#   "estimated_duration": "15 دقيقة",
#   "learning_path": [
#     {
#       "id": "step_1",
#       "type": "hook",
#       "title": "",
#       "content": "",
#       "teacher_message": "",
#       "action": ""
#     },
#     {
#       "id": "step_2",
#       "type": "warm_up_question",
#       "title": "",
#       "question": "",
#       "expected_answer": "",
#       "teacher_feedback": "",
#       "hint": ""
#     },
#     {
#       "id": "step_3",
#       "type": "guided_explanation",
#       "title": "",
#       "content": "",
#       "key_idea": "",
#       "checkpoint_question": "",
#       "checkpoint_answer": "",
#       "teacher_feedback": ""
#     },
#     {
#       "id": "step_4",
#       "type": "formal_definition",
#       "title": "",
#       "before_definition": "",
#       "definition": "",
#       "symbols": [
#         {
#           "symbol": "",
#           "meaning": ""
#         }
#       ],
#       "simple_meaning": "",
#       "memory_tip": ""
#     },
#     {
#       "id": "step_5",
#       "type": "method",
#       "title": "",
#       "method_goal": "",
#       "steps": [
#         {
#           "step_number": 1,
#           "instruction": "",
#           "why": "",
#           "calculation_template": "",
#           "student_task": "",
#           "hint": ""
#         }
#       ],
#       "conclusion_template": ""
#     },
#     {
#       "id": "step_6",
#       "type": "worked_example",
#       "title": "",
#       "example_statement": "",
#       "given_data": [],
#       "question": "",
#       "steps": [
#         {
#           "step_number": 1,
#           "title": "",
#           "teacher_explanation": "",
#           "calculation": "",
#           "result": "",
#           "next_question": ""
#         }
#       ],
#       "final_conclusion": ""
#     },
#     {
#       "id": "step_7",
#       "type": "common_mistakes",
#       "title": "",
#       "mistakes": [
#         {
#           "wrong_idea": "",
#           "why_wrong": "",
#           "correction": "",
#           "teacher_tip": ""
#         }
#       ]
#     },
#     {
#       "id": "step_8",
#       "type": "mini_quiz",
#       "title": "",
#       "questions": [
#         {
#           "question": "",
#           "choices": [],
#           "correct_answer": "",
#           "hint": "",
#           "explanation": ""
#         }
#       ]
#     }
#   ]
# }
#
# ==================================================
# بيانات الدرس
# ==================================================
#
# __LESSON_JSON__
# """
#
#         return prompt_template.replace(
#             "__LESSON_JSON__",
#             lesson_json,
#         ).strip()
#
#     def build_repair_prompt(
#         self,
#         raw_answer: str,
#         lesson_title: str,
#     ) -> str:
#         """
#         طلب ثانٍ فقط عند فشل Parsing.
#         يطلب من النموذج إعادة JSON أقصر بدلاً من مواصلة النص المقطوع.
#         """
#         raw_answer = raw_answer[:self.MAX_REPAIR_RAW_LENGTH]
#
#         repair_data = json.dumps(
#             {
#                 "lesson_title": lesson_title,
#                 "invalid_answer": raw_answer,
#             },
#             ensure_ascii=False,
#         )
#
#         return r"""
# أصلح الإجابة التالية وأعدها ككائن JSON صالح فقط.
#
# شروط إلزامية:
# - لا تكتب Markdown.
# - لا تكتب أي كلام قبل JSON أو بعده.
# - أغلق جميع النصوص والأقواس.
# - احذف أي مرحلة غير مكتملة.
# - احتفظ بالمراحل المكتملة.
# - اجعل learning_path قائمة.
# - لا تتجاوز 7 مراحل.
# - ضاعف الشرطة العكسية في أوامر LaTeX داخل JSON.
# - لا تستعمل $ أو $$ أو \[ \].
# - البنية العليا يجب أن تكون:
# {
#   "title": "",
#   "lesson_goal": "",
#   "estimated_duration": "15 دقيقة",
#   "learning_path": []
# }
#
# البيانات:
# __REPAIR_DATA__
# """.replace(
#             "__REPAIR_DATA__",
#             repair_data,
#         ).strip()
#
#     # =========================================================
#     # GENERATION
#     # =========================================================
#
#     def generate_with_context(
#         self,
#         cour: KnowledgeItem,
#         question: str,
#         prompt: str,
#     ):
#         context = BuiltContext(
#             question=question,
#             intent="explain_course",
#             context_text=prompt,
#             items=[cour],
#         )
#
#         return self.generator.generate(context)
#
#     def generate(self, axis_id: str):
#         try:
#             cour = (
#                 KnowledgeItem.objects
#                 .select_related("axis")
#                 .get(
#                     id=axis_id,
#                     item_type="lesson",
#                 )
#             )
#         except KnowledgeItem.DoesNotExist:
#             return None
#
#         lesson_title = self.normalize_text(
#             cour.title,
#             "درس رياضيات",
#         )
#
#         axis_title = (
#             self.normalize_text(cour.axis.title)
#             if cour.axis
#             else ""
#         )
#
#         lesson_content = self.limit_lesson_content(
#             cour.content
#         )
#
#         prompt = self.build_prompt(
#             axis_title=axis_title,
#             lesson_title=lesson_title,
#             lesson_content=lesson_content,
#         )
#
#         generated = self.generate_with_context(
#             cour=cour,
#             question=(
#                 f"اشرح درس {lesson_title} "
#                 "بطريقة مبسطة وتفاعلية."
#             ),
#             prompt=prompt,
#         )
#
#         extracted_answer = self.extract_json(
#             generated.answer
#         )
#
#         # إعادة محاولة واحدة فقط إذا بقي JSON غير صالح.
#         if "raw_answer" in extracted_answer:
#             repair_prompt = self.build_repair_prompt(
#                 raw_answer=extracted_answer["raw_answer"],
#                 lesson_title=lesson_title,
#             )
#
#             repaired_generated = self.generate_with_context(
#                 cour=cour,
#                 question="أصلح JSON المقطوع فقط.",
#                 prompt=repair_prompt,
#             )
#
#             repaired_answer = self.extract_json(
#                 repaired_generated.answer
#             )
#
#             if "raw_answer" not in repaired_answer:
#                 extracted_answer = repaired_answer
#                 generated = repaired_generated
#
#         if "raw_answer" in extracted_answer:
#             return {
#                 "mode": "cour_explication",
#                 "axis_id": str(cour.id),
#                 "axis_tag": (
#                     cour.axis.tag
#                     if cour.axis and hasattr(cour.axis, "tag")
#                     else ""
#                 ),
#                 "axis_title": axis_title,
#                 "lesson_title": lesson_title,
#                 "model": generated.model,
#                 "success": False,
#                 "error": "invalid_or_truncated_ai_json",
#                 "answer": {
#                     "title": lesson_title,
#                     "lesson_goal": "",
#                     "estimated_duration": "15 دقيقة",
#                     "learning_path": [],
#                 },
#             }
#
#         normalized_answer = self.normalize_answer(
#             extracted_answer
#         )
#
#         return {
#             "mode": "cour_explication",
#             "axis_id": str(cour.id),
#             "axis_tag": (
#                 cour.axis.tag
#                 if cour.axis and hasattr(cour.axis, "tag")
#                 else ""
#             ),
#             "axis_title": axis_title,
#             "lesson_title": lesson_title,
#             "model": generated.model,
#             "success": True,
#             "answer": normalized_answer,
#         }
# import json
# import re
# from typing import Any
#
# from knowledge.models import KnowledgeItem
# from knowledge.retrieval.answer_generator import AnswerGenerator
# from knowledge.retrieval.context_builder import BuiltContext
#
#
# class SolveBacExerciseService:
#     """
#     خدمة حل تمارين البكالوريا بطريقة تعليمية واضحة.
#
#     أهداف الخدمة:
#     - شرح طريقة الحساب، وليس عرض النتيجة فقط.
#     - توضيح الانتقال بين الأسطر الرياضية.
#     - استعمال LaTeX صالح للعرض في React.
#     - إرجاع JSON ثابت وسهل الاستعمال.
#     """
#
#     MAX_STEPS = 6
#     MAX_HINTS = 2
#
#     def __init__(self):
#         self.generator = AnswerGenerator()
#
#     # =========================================================
#     # JSON EXTRACTION
#     # =========================================================
#
#     LATEX_COMMANDS = (
#         "frac", "dfrac", "tfrac", "sqrt", "mathbb", "mathbf", "mathrm",
#         "text", "operatorname", "left", "right", "begin", "end", "cdot",
#         "times", "div", "pm", "mp", "le", "leq", "ge", "geq", "neq",
#         "infty", "to", "mapsto", "lim", "sum", "prod", "int", "ln",
#         "log", "exp", "sin", "cos", "tan", "arctan", "alpha", "beta",
#         "gamma", "delta", "lambda", "mu", "pi", "theta", "forall",
#         "exists", "in", "notin", "subset", "cup", "cap", "overline",
#         "underline", "vec", "overrightarrow", "overleftarrow"
#     )
#
#     def protect_latex_backslashes_in_json(self, text: str) -> str:
#         """
#         يجعل أوامر LaTeX صالحة داخل JSON قبل json.loads.
#
#         مثال:
#         \frac{x+2}{4-x}
#         يصبح داخل JSON:
#         \\frac{x+2}{4-x}
#
#         هذا يمنع json.loads من تفسير \f و\b و\t و\r كرموز تحكم.
#         """
#         if not text:
#             return ""
#
#         commands = "|".join(
#             sorted(map(re.escape, self.LATEX_COMMANDS), key=len, reverse=True)
#         )
#
#         # لا نضاعف الشرطة إذا كانت مضاعفة أصلاً.
#         text = re.sub(
#             rf"(?<!\\)\\(?=(?:{commands})\b)",
#             r"\\\\",
#             text,
#         )
#
#         # حماية محددات LaTeX داخل النص: \( \) \[ \]
#         text = re.sub(
#             r"(?<!\\)\\(?=[()\[\]])",
#             r"\\\\",
#             text,
#         )
#
#         return text
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
#         for attempt in attempts:
#             try:
#                 parsed = json.loads(attempt)
#                 if isinstance(parsed, dict):
#                     return parsed
#             except (json.JSONDecodeError, TypeError):
#                 continue
#
#         return {}
#
#     def extract_json(self, value: Any) -> dict:
#         if value is None:
#             return {}
#
#         if isinstance(value, dict):
#             return value
#
#         text = str(value).strip()
#         if not text:
#             return {}
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
#         parsed = self.parse_json_candidate(text)
#         if parsed:
#             return parsed
#
#         start = text.find("{")
#         end = text.rfind("}")
#         if start != -1 and end != -1 and end > start:
#             candidate = text[start:end + 1]
#             parsed = self.parse_json_candidate(candidate)
#             if parsed:
#                 return parsed
#
#         return {"raw_answer": text}
#
#     # =========================================================
#     # CLEANING AND LATEX REPAIR
#     # =========================================================
#
#     def restore_json_control_characters(self, text: str) -> str:
#         """
#         يصلح LaTeX إذا فُسرت بعض أوامره خطأ بواسطة JSON سابقاً.
#
#         أمثلة:
#         form-feed + rac  -> \frac
#         backspace + egin -> \begin
#         tab + o          -> \to
#         carriage + ight  -> \right
#         """
#         if not text:
#             return ""
#
#         repairs = {
#             "\x0crac": r"\frac",
#             "\x0cdfrac": r"\dfrac",
#             "\x0ctfrac": r"\tfrac",
#             "\x08egin": r"\begin",
#             "\x08eta": r"\beta",
#             "\t o": r"\to",
#             "\to": r"\to",
#             "\times": r"\times",
#             "\r ight": r"\right",
#             "\right": r"\right",
#         }
#
#         for old, new in repairs.items():
#             text = text.replace(old, new)
#
#         # حالات مباشرة ناتجة عن JSON: tab ثم بقية الأمر.
#         text = text.replace("\t" + "o", r"\to")
#         text = text.replace("\t" + "imes", r"\times")
#         text = text.replace("\r" + "ight", r"\right")
#         text = text.replace("\n" + "eq", r"\neq")
#         text = text.replace("\n" + "otin", r"\notin")
#
#         return text
#
#     def repair_latex_commands(self, text: str) -> str:
#         if not text:
#             return ""
#
#         # أوامر شائعة وصلتنا من دون الشرطة العكسية.
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
#             "leq", "ge", "geq", "neq", "infty", "to", "mapsto", "lim",
#             "sum", "prod", "int", "ln", "log", "exp", "sin", "cos",
#             "tan", "arctan", "alpha", "beta", "gamma", "delta", "lambda",
#             "mu", "pi", "theta", "forall", "exists", "notin", "subset",
#             "cup", "cap",
#         )
#
#         for command in simple_commands:
#             text = re.sub(
#                 rf"(?<![\\A-Za-z]){command}\b",
#                 rf"\\{command}",
#                 text,
#             )
#
#         # إصلاح الصيغ الممنوعة مثل \frac12 أو frac12.
#         text = re.sub(
#             r"\\(?:d?frac|tfrac)\s*([A-Za-z0-9])\s*([A-Za-z0-9])",
#             lambda m: rf"\frac{{{m.group(1)}}}{{{m.group(2)}}}",
#             text,
#         )
#
#         return text
#
#     def balance_latex_braces(self, text: str) -> str:
#         """يضيف الأقواس المغلقة الناقصة فقط، ولا يحذف أقواساً صحيحة."""
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
#         }
#
#         for old, new in replacements.items():
#             text = text.replace(old, new)
#
#         text = self.repair_latex_commands(text)
#         text = self.balance_latex_braces(text)
#         return text
#
#     def clean_string(self, value: Any) -> str:
#         text = self.normalize_latex_source(value)
#         if not text:
#             return ""
#
#         # لا نحذف \f أو \b أو \t عشوائياً لأنها قد تكون جزءاً من LaTeX.
#         text = text.replace("\r\n", "\n").replace("\r", "\n")
#         text = re.sub(r"[ ]{2,}", " ", text)
#         text = re.sub(r"\n{3,}", "\n\n", text)
#         return text.strip()
#
#     def clean_text(self, value: Any) -> str:
#         r"""
#         ينظف النص العربي مع الحفاظ على LaTeX المضمن بين \( و \).
#         """
#         text = self.clean_string(value)
#         if not text:
#             return ""
#
#         text = text.replace("$$", "")
#         text = re.sub(r"(?<!\\)\$(.+?)(?<!\\)\$", r"\\(\1\\)", text)
#         text = re.sub(r"^\s*#{1,6}\s*", "", text)
#
#         # إصلاح كل معادلة مضمنة بشكل مستقل.
#         def fix_inline(match: re.Match) -> str:
#             content = self.normalize_latex_source(match.group(1)).strip()
#             content = self.balance_latex_braces(content)
#             return rf"\({content}\)" if content else ""
#
#         text = re.sub(r"\\\((.*?)\\\)", fix_inline, text, flags=re.DOTALL)
#         return text.strip()
#
#     def clean_latex(self, value: Any, display: bool = True) -> str:
#         """ينظف LaTeX ويصلح الأوامر والأقواس قبل إرساله إلى React."""
#         latex_value = self.normalize_latex_source(value)
#         if not latex_value:
#             return ""
#
#         latex_value = latex_value.replace("$$", "")
#         latex_value = latex_value.replace("$", "")
#
#         latex_value = re.sub(r"^\s*\\\[\s*", "", latex_value)
#         latex_value = re.sub(r"\s*\\\]\s*$", "", latex_value)
#         latex_value = re.sub(r"^\s*\\\(\s*", "", latex_value)
#         latex_value = re.sub(r"\s*\\\)\s*$", "", latex_value)
#
#         latex_value = latex_value.replace("∞", r"\infty")
#         latex_value = latex_value.replace("→", r"\to")
#         latex_value = latex_value.replace("×", r"\times")
#         latex_value = latex_value.replace("÷", r"\div")
#         latex_value = latex_value.replace("≤", r"\leq")
#         latex_value = latex_value.replace("≥", r"\geq")
#         latex_value = latex_value.replace("≠", r"\neq")
#
#         latex_value = self.repair_latex_commands(latex_value)
#         latex_value = self.balance_latex_braces(latex_value)
#         latex_value = re.sub(r"[ ]{2,}", " ", latex_value).strip()
#
#         if not latex_value:
#             return ""
#
#         return rf"\[{latex_value}\]" if display else rf"\({latex_value}\)"
#
#     # =========================================================
#     # HELPERS
#     # =========================================================
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
#     def normalize_difficulty(self, value: Any) -> str:
#         difficulty = self.clean_text(value).lower()
#
#         mapping = {
#             "easy": "سهل",
#             "facile": "سهل",
#             "سهل": "سهل",
#
#             "medium": "متوسط",
#             "moyen": "متوسط",
#             "متوسط": "متوسط",
#
#             "hard": "صعب",
#             "difficile": "صعب",
#             "صعب": "صعب",
#         }
#
#         return mapping.get(
#             difficulty,
#             self.clean_text(value),
#         )
#
#     # =========================================================
#     # NORMALIZATION
#     # =========================================================
#
#     def normalize_hints(self, value: Any) -> list[dict]:
#         hints = []
#
#         for index, hint in enumerate(
#             self.ensure_list(value)[:self.MAX_HINTS],
#             start=1,
#         ):
#             if isinstance(hint, dict):
#                 text = self.clean_text(
#                     hint.get("text") or hint.get("hint")
#                 )
#
#                 math_value = self.clean_latex(
#                     hint.get("math"),
#                     display=True,
#                 )
#             else:
#                 text = self.clean_text(hint)
#                 math_value = ""
#
#             if not text and not math_value:
#                 continue
#
#             hints.append({
#                 "number": index,
#                 "text": text,
#                 "math": math_value,
#             })
#
#         return hints
#
#     def normalize_calculation_lines(self, value: Any) -> list[dict]:
#         """
#         ينظم الأسطر التي تشرح الانتقال بين العمليات الحسابية.
#         """
#
#         lines = []
#
#         for index, line in enumerate(
#             self.ensure_list(value),
#             start=1,
#         ):
#             if not isinstance(line, dict):
#                 continue
#
#             explanation = self.clean_text(
#                 line.get("explanation")
#                 or line.get("text")
#             )
#
#             math_value = self.clean_latex(
#                 line.get("math"),
#                 display=True,
#             )
#
#             if not explanation and not math_value:
#                 continue
#
#             lines.append({
#                 "number": index,
#                 "explanation": explanation,
#                 "math": math_value,
#             })
#
#         return lines
#
#     def normalize_steps(self, value: Any) -> list[dict]:
#         steps = []
#
#         for index, step in enumerate(
#             self.ensure_list(value)[:self.MAX_STEPS],
#             start=1,
#         ):
#             if not isinstance(step, dict):
#                 continue
#
#             title = self.clean_text(
#                 step.get("title") or f"الخطوة {index}"
#             )
#
#             explanation = self.clean_text(
#                 step.get("explanation")
#             )
#
#             calculation_lines = self.normalize_calculation_lines(
#                 step.get("calculation_lines")
#             )
#
#             math_value = self.clean_latex(
#                 step.get("math"),
#                 display=True,
#             )
#
#             conclusion = self.clean_text(
#                 step.get("conclusion")
#                 or step.get("result")
#             )
#
#             if not any([
#                 explanation,
#                 calculation_lines,
#                 math_value,
#                 conclusion,
#             ]):
#                 continue
#
#             steps.append({
#                 "number": index,
#                 "title": title,
#                 "explanation": explanation,
#                 "calculation_lines": calculation_lines,
#                 "math": math_value,
#                 "conclusion": conclusion,
#             })
#
#         return steps
#
#     def normalize_answer(
#         self,
#         answer: dict,
#         exercise: KnowledgeItem,
#     ) -> dict:
#         if not isinstance(answer, dict):
#             answer = {}
#
#         axis = exercise.axis
#         metadata = exercise.metadata or {}
#
#         return {
#             "exercise_title": self.clean_text(
#                 answer.get("exercise_title")
#                 or exercise.exercise_title
#                 or exercise.title
#             ),
#
#             "axis_title": self.clean_text(
#                 answer.get("axis_title")
#                 or (
#                     axis.title
#                     if axis
#                     else metadata.get("axis_title", "")
#                 )
#             ),
#
#             "year": self.clean_text(
#                 answer.get("year")
#                 or exercise.year
#             ),
#
#             "difficulty": self.normalize_difficulty(
#                 answer.get("difficulty")
#                 or exercise.difficulty
#             ),
#
#             "question": self.clean_text(
#                 answer.get("question")
#                 or exercise.content
#             ),
#
#             "question_latex": self.clean_latex(
#                 answer.get("question_latex"),
#                 display=True,
#             ),
#
#             "intro": self.clean_text(
#                 answer.get("intro")
#             ),
#
#             "idea": self.clean_text(
#                 answer.get("idea")
#             ),
#
#             "hints": self.normalize_hints(
#                 answer.get("hints")
#             ),
#
#             "solution_steps": self.normalize_steps(
#                 answer.get("solution_steps")
#             ),
#
#             "final_answer": self.clean_text(
#                 answer.get("final_answer")
#             ),
#
#             "final_math": self.clean_latex(
#                 answer.get("final_math"),
#                 display=True,
#             ),
#
#             "remember": self.clean_text(
#                 answer.get("remember")
#             ),
#
#             "common_mistake": self.clean_text(
#                 answer.get("common_mistake")
#             ),
#
#             "check_understanding": self.clean_text(
#                 answer.get("check_understanding")
#                 or answer.get("next_question")
#             ),
#         }
#
#     # =========================================================
#     # PROMPT
#     # =========================================================
#
#     def build_prompt(self, exercise: KnowledgeItem) -> str:
#         axis = exercise.axis
#         metadata = exercise.metadata or {}
#
#         exercise_data = {
#             "id": str(exercise.id),
#             "title": exercise.title or "",
#             "content": exercise.content or "",
#             "year": exercise.year or "",
#             "exercise_title": exercise.exercise_title or "",
#             "question_number": exercise.question_number or "",
#             "points": exercise.points or "",
#             "difficulty": exercise.difficulty or "",
#             "axis_title": (
#                 axis.title
#                 if axis
#                 else metadata.get("axis_title", "")
#             ),
#             "axis_tag": (
#                 axis.tag
#                 if axis
#                 else metadata.get("axis_tag", "")
#             ),
#         }
#
#         exercise_json = json.dumps(
#             exercise_data,
#             ensure_ascii=False,
#             indent=2,
#         )
#
#         # IMPORTANT:
#         # هذا النص ليس f-string عمداً. وجود أقواس LaTeX مثل {x+2}
#         # داخل f-string يجعل Python يحاول تنفيذها كتعابير Python.
#         prompt_template = r"""
# أنت أستاذ رياضيات جزائري ممتاز تشرح لتلميذ بكالوريا بطريقة سهلة،
# جميلة، طبيعية، ومفهومة.
#
# المطلوب ليس فقط إعطاء الجواب النهائي، بل شرح طريقة الحساب بوضوح.
# اشرح كما يشرح أستاذ داخل القسم، وليس كآلة تعرض معادلات فقط.
#
# ==================================================
# أولاً: أسلوب الحل
# ==================================================
#
# 1. ابدأ بجملة قصيرة ومريحة.
# 2. اشرح الحل في خطوتين إلى ست خطوات فقط.
# 3. اجعل كل شرح قصيراً ومباشراً.
# 4. لا تكرر نفس الفكرة.
# 5. اختر الطريقة الأسهل والأوضح فقط.
# 6. إذا كان السؤال يحتوي عدة مطالب، حلها بالترتيب.
# 7. لا تخترع معلومات غير موجودة في السؤال.
#
# استعمل عبارات طبيعية مثل:
# - نعوض مباشرة.
# - نوحد المقامات.
# - نجمع الحدود المتشابهة.
# - نرتب العبارة.
# - نخرج العامل المشترك.
# - نلاحظ أن...
# - بما أن...
# - إذن...
#
# ==================================================
# ثانياً: شرح الحساب
# ==================================================
#
# اشرح العمليات المهمة فقط.
#
# أمثلة داخل النص العربي:
# - نعوض \(u_{n+1}\) بالعلاقة المعطاة.
# - نوحد المقام بكتابة \(2=\frac{6}{3}\).
# - نخرج العامل المشترك \(x-1\).
# - نكتب \(f(x)=\frac{x+2}{4-x}\).
#
# ==================================================
# ثالثاً: تنظيم الخطوات
# ==================================================
#
# كل خطوة تحتوي:
# - title: عنوان قصير.
# - explanation: شرح بسيط.
# - calculation_lines: مراحل الحساب.
# - math: الحساب الكامل للخطوة.
# - conclusion: استنتاج قصير عند الحاجة.
#
# مثال JSON صحيح:
# {
#   "title": "حساب الفرق",
#   "explanation": "نحسب الفرق بين حدين متتاليين.",
#   "calculation_lines": [
#     {
#       "explanation": "نعوض الحد بالعلاقة المعطاة.",
#       "math": "u_{n+1}-u_n=\\frac{2}{3}u_n+2-u_n"
#     },
#     {
#       "explanation": "نجمع الحدود المتشابهة.",
#       "math": "\\frac{2}{3}u_n-u_n=-\\frac{1}{3}u_n"
#     }
#   ],
#   "math": "u_{n+1}-u_n=\\frac{6-u_n}{3}",
#   "conclusion": "إشارة الفرق مرتبطة بإشارة 6-u_n."
# }
#
# ==================================================
# رابعاً: قواعد LaTeX وJSON
# ==================================================
#
# 1. كل تعبير رياضي داخل النص العربي يوضع بين \( و \).
# 2. حقول math تحتوي LaTeX فقط، دون نص عربي.
# 3. لا تضع داخل حقول math: \( \) أو \[ \] أو $ أو $$.
# 4. لأن الناتج JSON، يجب مضاعفة كل شرطة عكسية داخل قيم JSON.
#
# مثال صحيح داخل JSON:
# "f(x)=\\frac{x+2}{4-x}"
#
# أمثلة صحيحة:
# \frac{a}{b}
# \sqrt{x}
# u_{n+1}
# x^{2}
# \mathbb{N}
# \left(x+1\right)
# \begin{aligned}
# f(x)&=\frac{x+2}{4-x}\\
# f'(x)&=\frac{6}{(4-x)^2}
# \end{aligned}
#
# ممنوع:
# 2/3
# frac23
# \frac23
# u(n+1)
# un+1
# $...$
# $$...$$
#
# ==================================================
# خامساً: بنية JSON المطلوبة
# ==================================================
#
# أرجع JSON صالحاً فقط.
# لا تكتب شيئاً قبل JSON أو بعده.
# لا تستعمل Markdown.
# لا تضف حقولاً أخرى.
#
# {
#   "exercise_title": "",
#   "axis_title": "",
#   "year": "",
#   "difficulty": "",
#   "question": "",
#   "question_latex": "",
#   "intro": "",
#   "idea": "",
#   "hints": [
#     {
#       "text": "",
#       "math": ""
#     }
#   ],
#   "solution_steps": [
#     {
#       "title": "",
#       "explanation": "",
#       "calculation_lines": [
#         {
#           "explanation": "",
#           "math": ""
#         }
#       ],
#       "math": "",
#       "conclusion": ""
#     }
#   ],
#   "final_answer": "",
#   "final_math": "",
#   "remember": "",
#   "common_mistake": "",
#   "check_understanding": ""
# }
#
# ==================================================
# سادساً: جودة الجواب
# ==================================================
#
# يجب أن يكون الحل:
# - صحيحاً رياضياً.
# - بسيطاً ومفهوماً.
# - لا يقفز بين العمليات.
# - لا يكون طويلاً أو مملاً.
# - مناسباً لتلميذ بكالوريا.
# - يحتوي LaTeX صحيحاً وJSON صالحاً.
#
# ==================================================
# بيانات التمرين
# ==================================================
#
# __EXERCISE_JSON__
# """
#
#         return prompt_template.replace(
#             "__EXERCISE_JSON__",
#             exercise_json,
#         ).strip()
#
#     # =========================================================
#     # GENERATE
#     # =========================================================
#
#     def generate(self, exercise_id: str):
#         try:
#             exercise = (
#                 KnowledgeItem.objects
#                 .select_related("axis")
#                 .get(
#                     id=exercise_id,
#                     item_type="bac_question",
#                 )
#             )
#         except KnowledgeItem.DoesNotExist:
#             return None
#
#         prompt = self.build_prompt(exercise)
#
#         context = BuiltContext(
#             question=exercise.content,
#             intent="solve_bac_exercise",
#             context_text=prompt,
#             items=[exercise],
#         )
#
#         generated = self.generator.generate(context)
#
#         extracted_answer = self.extract_json(
#             generated.answer
#         )
#
#         if "raw_answer" in extracted_answer:
#             return {
#                 "mode": "solve_bac_exercise",
#                 "exercise_id": str(exercise.id),
#                 "model": generated.model,
#                 "success": False,
#                 "error": "invalid_ai_json",
#                 "raw_answer": extracted_answer["raw_answer"],
#                 "answer": None,
#             }
#
#         normalized_answer = self.normalize_answer(
#             extracted_answer,
#             exercise,
#         )
#
#         return {
#             "mode": "solve_bac_exercise",
#             "exercise_id": str(exercise.id),
#             "model": generated.model,
#             "success": True,
#             "answer": normalized_answer,
#         }


import json
import re
from typing import Any

from course.models import Question
from knowledge.retrieval.answer_generator import AnswerGenerator
from knowledge.retrieval.context_builder import BuiltContext


class SolveBacExerciseService:
    """
    خدمة حل تمارين البكالوريا بطريقة تعليمية واضحة.

    أهداف الخدمة:
    - شرح طريقة الحساب، وليس عرض النتيجة فقط.
    - توضيح الانتقال بين الأسطر الرياضية.
    - استعمال LaTeX صالح للعرض في React وMathJax.
    - فصل الشرح العربي عن الحسابات الطويلة.
    - إرجاع JSON ثابت وسهل الاستعمال.
    """

    MAX_STEPS = 6
    MAX_HINTS = 2
    MAX_CALCULATION_LINES = 8

    LATEX_COMMANDS = (
        "frac", "dfrac", "tfrac", "sqrt", "mathbb", "mathbf", "mathrm",
        "text", "operatorname", "left", "right", "begin", "end", "cdot",
        "times", "div", "pm", "mp", "le", "leq", "ge", "geq", "neq",
        "approx", "sim", "equiv", "infty", "to", "mapsto", "lim", "sum",
        "prod", "int", "ln", "log", "exp", "sin", "cos", "tan", "arctan",
        "alpha", "beta", "gamma", "delta", "lambda", "mu", "pi", "theta",
        "forall", "exists", "in", "notin", "subset", "subseteq", "supset",
        "supseteq", "cup", "cap", "overline", "underline", "vec",
        "overrightarrow", "overleftarrow", "geqslant", "leqslant"
    )

    def __init__(self):
        self.generator = AnswerGenerator()

    # =========================================================
    # JSON EXTRACTION
    # =========================================================

    def protect_latex_backslashes_in_json(self, text: str) -> str:
        """
        يحمي أوامر LaTeX داخل JSON قبل json.loads.

        مثال:
            \frac{x+2}{4-x}

        يصبح:
            \\frac{x+2}{4-x}

        وذلك حتى لا يفسر json.loads أوامر مثل:
        \f و \b و \t و \r كرموز تحكم.
        """
        if not text:
            return ""

        commands = "|".join(
            sorted(
                map(re.escape, self.LATEX_COMMANDS),
                key=len,
                reverse=True,
            )
        )

        # مضاعفة الشرطة العكسية المفردة قبل أوامر LaTeX المعروفة.
        text = re.sub(
            rf"(?<!\\)\\(?=(?:{commands})\b)",
            r"\\\\",
            text,
        )

        # حماية محددات LaTeX داخل النصوص.
        text = re.sub(
            r"(?<!\\)\\(?=[()\[\]])",
            r"\\\\",
            text,
        )

        return text

    def parse_json_candidate(self, candidate: str) -> dict:
        if not candidate:
            return {}

        attempts = (
            candidate,
            self.protect_latex_backslashes_in_json(candidate),
        )

        for attempt in attempts:
            try:
                parsed = json.loads(attempt)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

        return {}

    def extract_json(self, value: Any) -> dict:
        """
        يستخرج JSON من جواب النموذج حتى لو أُحيط بـ Markdown.
        """
        if value is None:
            return {}

        if isinstance(value, dict):
            return value

        text = str(value).strip()
        if not text:
            return {}

        # حذف code fences إن وُجدت.
        text = re.sub(
            r"^\s*```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\s*```\s*$",
            "",
            text,
            flags=re.IGNORECASE,
        )

        parsed = self.parse_json_candidate(text)
        if parsed:
            return parsed

        # محاولة استخراج أول كائن JSON كامل تقريباً.
        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1 and end > start:
            candidate = text[start:end + 1]
            parsed = self.parse_json_candidate(candidate)

            if parsed:
                return parsed

        return {"raw_answer": text}

    # =========================================================
    # CLEANING AND LATEX REPAIR
    # =========================================================

    def restore_json_control_characters(self, text: str) -> str:
        """
        يصلح بعض أوامر LaTeX التي قد تتحول إلى رموز تحكم بعد JSON.

        أمثلة:
            form-feed + rac  -> \frac
            backspace + egin -> \begin
            tab + o          -> \to
            carriage + ight  -> \right
        """
        if not text:
            return ""

        repairs = {
            "\x0crac": r"\frac",
            "\x0cdfrac": r"\dfrac",
            "\x0ctfrac": r"\tfrac",
            "\x08egin": r"\begin",
            "\x08eta": r"\beta",
            "\t" + "o": r"\to",
            "\t" + "imes": r"\times",
            "\r" + "ight": r"\right",
            "\n" + "eq": r"\neq",
            "\n" + "otin": r"\notin",
        }

        for old, new in repairs.items():
            text = text.replace(old, new)

        return text

    def repair_latex_commands(self, text: str) -> str:
        """
        يصلح أوامر LaTeX الشائعة إذا أرسلها النموذج بدون شرطة عكسية.
        """
        if not text:
            return ""

        commands_with_brace = (
            "frac", "dfrac", "tfrac", "sqrt", "mathbb", "mathbf",
            "mathrm", "text", "operatorname", "begin", "end",
            "overline", "underline", "vec", "overrightarrow",
            "overleftarrow",
        )

        for command in commands_with_brace:
            text = re.sub(
                rf"(?<![\\A-Za-z]){command}\s*\{{",
                rf"\\{command}{{",
                text,
            )

        simple_commands = (
            "left", "right", "cdot", "times", "div", "pm", "mp", "le",
            "leq", "ge", "geq", "neq", "approx", "sim", "equiv",
            "infty", "to", "mapsto", "lim", "sum", "prod", "int", "ln",
            "log", "exp", "sin", "cos", "tan", "arctan", "alpha", "beta",
            "gamma", "delta", "lambda", "mu", "pi", "theta", "forall",
            "exists", "notin", "subset", "subseteq", "supset", "supseteq",
            "cup", "cap", "geqslant", "leqslant",
        )

        for command in simple_commands:
            text = re.sub(
                rf"(?<![\\A-Za-z]){command}\b",
                rf"\\{command}",
                text,
            )

        # إصلاح صيغ مثل \frac23 إلى \frac{2}{3}.
        text = re.sub(
            r"\\(?:d?frac|tfrac)\s*([A-Za-z0-9])\s*([A-Za-z0-9])",
            lambda match: (
                rf"\frac{{{match.group(1)}}}{{{match.group(2)}}}"
            ),
            text,
        )

        return text

    def balance_latex_braces(self, text: str) -> str:
        """
        يضيف الأقواس المغلقة الناقصة فقط.
        لا يحذف الأقواس الموجودة.
        """
        if not text:
            return ""

        balance = 0
        escaped = False

        for char in text:
            if escaped:
                escaped = False
                continue

            if char == "\\":
                escaped = True
            elif char == "{":
                balance += 1
            elif char == "}" and balance > 0:
                balance -= 1

        if balance > 0:
            text += "}" * balance

        return text

    def normalize_latex_source(self, value: Any) -> str:
        if value is None:
            return ""

        text = str(value)
        text = self.restore_json_control_characters(text)

        replacements = {
            "\u200b": "",
            "\u200c": "",
            "\u200d": "",
            "\ufeff": "",
            "```json": "",
            "```latex": "",
            "```math": "",
            "```": "",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        text = self.repair_latex_commands(text)
        text = self.balance_latex_braces(text)

        return text

    def clean_string(self, value: Any) -> str:
        text = self.normalize_latex_source(value)

        if not text:
            return ""

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def add_spaces_around_inline_math(self, text: str) -> str:
        """
        يفرض مسافة قبل وبعد \( ... \) لمنع التصاق العربية بالمعادلة.
        """
        if not text:
            return ""

        text = re.sub(r"\s*\\\(", r" \\(", text)
        text = re.sub(r"\\\)\s*", r"\\) ", text)
        text = re.sub(r"[ ]{2,}", " ", text)

        return text.strip()

    def clean_text(self, value: Any) -> str:
        r"""
        ينظف النص العربي ويحافظ على LaTeX المضمن بين \( و \).
        """
        text = self.clean_string(value)

        if not text:
            return ""

        text = text.replace("$$", "")
        text = re.sub(
            r"(?<!\\)\$(.+?)(?<!\\)\$",
            r"\\(\1\\)",
            text,
            flags=re.DOTALL,
        )
        text = re.sub(r"^\s*#{1,6}\s*", "", text)

        def fix_inline(match: re.Match) -> str:
            content = self.normalize_latex_source(match.group(1)).strip()
            content = self.balance_latex_braces(content)

            if not content:
                return ""

            return rf"\({content}\)"

        text = re.sub(
            r"\\\((.*?)\\\)",
            fix_inline,
            text,
            flags=re.DOTALL,
        )

        text = self.add_spaces_around_inline_math(text)
        text = re.sub(r"[ ]{2,}", " ", text)

        return text.strip()

    def clean_latex(self, value: Any, display: bool = True) -> str:
        """
        ينظف LaTeX قبل إرساله إلى React.

        display=True:
            يرجع \[ ... \]

        display=False:
            يرجع \( ... \)
        """
        latex_value = self.normalize_latex_source(value)

        if not latex_value:
            return ""

        # حذف المحددات لأن الخدمة ستضيف المحدد المناسب بنفسها.
        latex_value = latex_value.replace("$$", "")
        latex_value = latex_value.replace("$", "")

        latex_value = re.sub(
            r"^\s*\\\[\s*",
            "",
            latex_value,
        )
        latex_value = re.sub(
            r"\s*\\\]\s*$",
            "",
            latex_value,
        )
        latex_value = re.sub(
            r"^\s*\\\(\s*",
            "",
            latex_value,
        )
        latex_value = re.sub(
            r"\s*\\\)\s*$",
            "",
            latex_value,
        )

        replacements = {
            "∞": r"\infty",
            "→": r"\to",
            "×": r"\times",
            "÷": r"\div",
            "≤": r"\leq",
            "≥": r"\geq",
            "≠": r"\neq",
            "≈": r"\approx",
        }

        for old, new in replacements.items():
            latex_value = latex_value.replace(old, new)

        latex_value = self.repair_latex_commands(latex_value)
        latex_value = self.balance_latex_braces(latex_value)
        latex_value = re.sub(r"[ \t]{2,}", " ", latex_value).strip()

        if not latex_value:
            return ""

        if display:
            return rf"\[{latex_value}\]"

        return rf"\({latex_value}\)"

    # =========================================================
    # HELPERS
    # =========================================================

    def ensure_list(self, value: Any) -> list:
        if isinstance(value, list):
            return value

        if value in (None, ""):
            return []

        return [value]

    def normalize_difficulty(self, value: Any) -> str:
        original = self.clean_text(value)
        difficulty = original.lower()

        mapping = {
            "easy": "سهل",
            "facile": "سهل",
            "سهل": "سهل",
            "medium": "متوسط",
            "moyen": "متوسط",
            "متوسط": "متوسط",
            "hard": "صعب",
            "difficile": "صعب",
            "صعب": "صعب",
        }

        return mapping.get(difficulty, original)

    # =========================================================
    # NORMALIZATION
    # =========================================================

    def normalize_hints(self, value: Any) -> list[dict]:
        hints = []

        for index, hint in enumerate(
            self.ensure_list(value)[:self.MAX_HINTS],
            start=1,
        ):
            if isinstance(hint, dict):
                text = self.clean_text(
                    hint.get("text")
                    or hint.get("hint")
                )
                math_value = self.clean_latex(
                    hint.get("math"),
                    display=True,
                )
            else:
                text = self.clean_text(hint)
                math_value = ""

            if not text and not math_value:
                continue

            hints.append({
                "number": index,
                "text": text,
                "math": math_value,
            })

        return hints

    def normalize_calculation_lines(self, value: Any) -> list[dict]:
        """
        ينظم أسطر الحساب، بحيث يحتوي كل سطر على انتقال واحد واضح.
        """
        lines = []

        for index, line in enumerate(
            self.ensure_list(value)[:self.MAX_CALCULATION_LINES],
            start=1,
        ):
            if not isinstance(line, dict):
                continue

            explanation = self.clean_text(
                line.get("explanation")
                or line.get("text")
            )
            math_value = self.clean_latex(
                line.get("math"),
                display=True,
            )

            if not explanation and not math_value:
                continue

            lines.append({
                "number": index,
                "explanation": explanation,
                "math": math_value,
            })

        return lines

    def normalize_steps(self, value: Any) -> list[dict]:
        steps = []

        for index, step in enumerate(
            self.ensure_list(value)[:self.MAX_STEPS],
            start=1,
        ):
            if not isinstance(step, dict):
                continue

            title = self.clean_text(
                step.get("title")
                or f"الخطوة {index}"
            )
            explanation = self.clean_text(
                step.get("explanation")
            )
            calculation_lines = self.normalize_calculation_lines(
                step.get("calculation_lines")
            )
            math_value = self.clean_latex(
                step.get("math"),
                display=True,
            )
            conclusion = self.clean_text(
                step.get("conclusion")
                or step.get("result")
            )

            if not any(
                (
                    explanation,
                    calculation_lines,
                    math_value,
                    conclusion,
                )
            ):
                continue

            steps.append({
                "number": index,
                "title": title,
                "explanation": explanation,
                "calculation_lines": calculation_lines,
                "math": math_value,
                "conclusion": conclusion,
            })

        return steps

    def normalize_answer(
        self,
        answer: dict,
        exercise: Question,
    ) -> dict:
        if not isinstance(answer, dict):
            answer = {}

        axis = exercise.axis
        metadata = exercise.metadata or {}

        return {
            "exercise_title": self.clean_text(
                answer.get("exercise_title")
                or exercise.exercise_title
                or exercise.title
            ),
            "axis_title": self.clean_text(
                answer.get("axis_title")
                or (
                    axis.title
                    if axis
                    else metadata.get("axis_title", "")
                )
            ),
            "year": self.clean_text(
                answer.get("year")
                or exercise.year
            ),
            "difficulty": self.normalize_difficulty(
                answer.get("difficulty")
                or exercise.difficulty
            ),
            "question": self.clean_text(
                answer.get("question")
                or exercise.content
            ),
            "question_latex": self.clean_latex(
                answer.get("question_latex"),
                display=True,
            ),
            "intro": self.clean_text(
                answer.get("intro")
            ),
            "idea": self.clean_text(
                answer.get("idea")
            ),
            "hints": self.normalize_hints(
                answer.get("hints")
            ),
            "solution_steps": self.normalize_steps(
                answer.get("solution_steps")
            ),
            "final_answer": self.clean_text(
                answer.get("final_answer")
            ),
            "final_math": self.clean_latex(
                answer.get("final_math"),
                display=True,
            ),
            "remember": self.clean_text(
                answer.get("remember")
            ),
            "common_mistake": self.clean_text(
                answer.get("common_mistake")
            ),
            "check_understanding": self.clean_text(
                answer.get("check_understanding")
                or answer.get("next_question")
            ),
        }

    # =========================================================
    # PROMPT
    # =========================================================

    def build_prompt(self, exercise: Question) -> str:
        axis = exercise.axis
        metadata = exercise.metadata or {}

        exercise_data = {
            "id": str(exercise.id),
            "title": exercise.title or "",
            "content": exercise.content or "",
            "year": exercise.year or "",
            "exercise_title": exercise.exercise_title or "",
            "question_number": exercise.question_number or "",
            "points": exercise.points or "",
            "difficulty": exercise.difficulty or "",
            "axis_title": (
                axis.title
                if axis
                else metadata.get("axis_title", "")
            ),
            "axis_tag": (
                axis.tag
                if axis
                else metadata.get("axis_tag", "")
            ),
        }

        exercise_json = json.dumps(
            exercise_data,
            ensure_ascii=False,
            indent=2,
        )

        # ليس f-string لأن أمثلة LaTeX تحتوي أقواساً مثل {x+2}.
        prompt_template = r"""
أنت أستاذ رياضيات جزائري ممتاز، تشرح لتلميذ بكالوريا
بطريقة سهلة، واضحة، جميلة، وطبيعية.

المطلوب ليس عرض النتيجة النهائية فقط.
اشرح طريقة التفكير والحساب كما يشرح أستاذ داخل القسم،
لكن من دون إطالة أو تكرار.

==================================================
أولاً: أسلوب الحل
==================================================

1. ابدأ بجملة قصيرة ومريحة توضح فكرة السؤال.
2. حل التمرين في خطوتين إلى ست خطوات فقط.
3. اجعل كل خطوة تعالج فكرة واحدة.
4. اجعل الشرح قصيراً، مباشراً، وسهل الفهم.
5. لا تكرر نفس الفكرة أو نفس المعادلة.
6. اختر أبسط طريقة صحيحة.
7. إذا كان السؤال يحتوي عدة مطالب، حلها بالترتيب.
8. لا تخترع أي معلومة غير موجودة في نص التمرين.
9. لا تقفز من عملية إلى نتيجة بعيدة دون توضيح.
10. لا تستعمل عبارات عامة مبهمة مثل:
    "بالحساب نجد" دون إظهار الحساب المهم.

استعمل عبارات طبيعية مثل:
- نعوض مباشرة.
- نوحد المقامات.
- نجمع الحدود المتشابهة.
- نرتب العبارة.
- نخرج العامل المشترك.
- ندرس الإشارة.
- نلاحظ أن...
- بما أن...
- ومنه...
- إذن...

==================================================
ثانياً: شرح الحساب
==================================================

اشرح العمليات المهمة فقط.

كل انتقال حسابي مهم يوضع في calculation_lines مستقلة.

لا تجمع عدداً كبيراً من التحويلات في معادلة واحدة طويلة.

مثال جيد:
- السطر الأول: نعوض بالعلاقة المعطاة.
- السطر الثاني: نجمع الحدود المتشابهة.
- السطر الثالث: نبسط الكسر.
- ثم نستنتج النتيجة.

أمثلة صحيحة داخل النص العربي:
- نعوض \(u_{n+1}\) بالعلاقة المعطاة.
- نوحد المقام بكتابة \(2=\frac{6}{3}\).
- نخرج العامل المشترك \(x-1\).
- ندرس إشارة \(u_{n+1}-u_n\).

مهم جداً:
يجب ترك مسافة قبل وبعد كل تعبير رياضي داخل النص العربي.

صحيح:
لدينا \(u_n\) متتالية عددية.

خطأ:
لدينا\(u_n\)متتالية عددية.

==================================================
ثالثاً: تنظيم كل خطوة
==================================================

كل خطوة تحتوي على:

- title:
  عنوان قصير وواضح.

- explanation:
  شرح عربي قصير للفكرة، من دون حساب طويل.

- calculation_lines:
  قائمة مراحل الحساب.
  كل عنصر يحتوي شرحاً قصيراً ومعادلة واحدة واضحة.

- math:
  النتيجة الرياضية الأساسية للخطوة.
  يمكن تركه فارغاً إذا كانت calculation_lines كافية.

- conclusion:
  استنتاج قصير عند الحاجة.

مثال صحيح:

{
  "title": "حساب الفرق",
  "explanation": "نحسب الفرق بين حدين متتاليين لدراسة اتجاه التغير.",
  "calculation_lines": [
    {
      "explanation": "نعوض الحد بالعلاقة المعطاة.",
      "math": "u_{n+1}-u_n=\\frac{2}{3}u_n+2-u_n"
    },
    {
      "explanation": "نجمع الحدود المتشابهة.",
      "math": "\\frac{2}{3}u_n-u_n=-\\frac{1}{3}u_n"
    },
    {
      "explanation": "نوحد الكتابة في كسر واحد.",
      "math": "u_{n+1}-u_n=\\frac{6-u_n}{3}"
    }
  ],
  "math": "",
  "conclusion": "إشارة الفرق هي إشارة \(6-u_n\)."
}

==================================================
رابعاً: قواعد كتابة النصوص الرياضية
==================================================

يجب أن يكون الناتج مناسباً للعرض داخل React باستعمال MathJax.

1. أي تعبير رياضي داخل النص العربي يجب أن يكون بين:
   \( و \)

مثال صحيح:
نعوض \(u_{n+1}\) بالعلاقة المعطاة.

مثال خطأ:
نعوض u_{n+1} بالعلاقة المعطاة.

2. اترك دائماً مسافة قبل وبعد التعبير الرياضي داخل النص.

صحيح:
بما أن \(u_n<6\) فإن الفرق موجب.

خطأ:
بما أن\(u_n<6\)فإن الفرق موجب.

3. لا تكتب معادلة طويلة داخل explanation أو conclusion.

إذا كانت المعادلة تحتاج عدة تحولات،
ضعها في calculation_lines أو math.

4. حقول math تحتوي LaTeX فقط.

صحيح:
"math": "x^{2}+3x+2=0"

خطأ:
"math": "نحسب x^{2}+3x+2=0"

5. لا تضع داخل حقول math أياً من المحددات التالية:

\( \)
\[ \]
$
$$

التطبيق سيضيف المحددات تلقائياً.

6. اكتب الكسور دائماً هكذا:

\frac{2}{3}

ولا تكتب:

2/3
frac23
\frac23

7. استعمل الصيغة الصحيحة للفهارس والأسس:

u_{n+1}
u_{0}
x^{2}
a_{k-1}

ولا تكتب:

un+1
u(n+1)
x2

8. استعمل أوامر LaTeX الصحيحة:

\sqrt{x}
\mathbb{N}
\left(x+1\right)
\leq
\geq
\neq
\infty
\to

9. عند وجود عدة أسطر حسابية،
ضع كل انتقال في عنصر مستقل داخل calculation_lines.

10. لا تكتب نصاً عربياً داخل:
\begin{aligned} ... \end{aligned}

الأفضل استعمال calculation_lines منفصلة.

==================================================
خامساً: قواعد JSON
==================================================

1. أرجع كائن JSON صالحاً فقط.
2. لا تكتب أي شيء قبل JSON أو بعده.
3. لا تستعمل Markdown.
4. لا تستعمل code fences.
5. لا تضف حقولاً غير مطلوبة.
6. لا تحذف أي حقل من البنية المطلوبة.
7. إذا لم يكن الحقل ضرورياً، أرجع قيمة فارغة مناسبة:
   "" أو [].
8. داخل قيم JSON يجب مضاعفة كل شرطة عكسية
   خاصة بأوامر LaTeX.

مثال صحيح داخل JSON:

"math": "u_{n+1}=\\frac{2}{3}u_n+2"

وليس:

"math": "u_{n+1}=\frac{2}{3}u_n+2"

==================================================
سادساً: بنية JSON المطلوبة
==================================================

{
  "exercise_title": "",
  "axis_title": "",
  "year": "",
  "difficulty": "",
  "question": "",
  "question_latex": "",
  "intro": "",
  "idea": "",
  "hints": [
    {
      "text": "",
      "math": ""
    }
  ],
  "solution_steps": [
    {
      "title": "",
      "explanation": "",
      "calculation_lines": [
        {
          "explanation": "",
          "math": ""
        }
      ],
      "math": "",
      "conclusion": ""
    }
  ],
  "final_answer": "",
  "final_math": "",
  "remember": "",
  "common_mistake": "",
  "check_understanding": ""
}

==================================================
سابعاً: جودة الجواب
==================================================

يجب أن يكون الحل:

- صحيحاً رياضياً.
- بسيطاً ومفهوماً.
- منظماً خطوة بخطوة.
- غير طويل أو ممل.
- مناسباً لتلميذ بكالوريا.
- خالياً من التكرار.
- خالياً من القفزات الحسابية.
- يحتوي LaTeX صحيحاً.
- يحتوي JSON صالحاً.
- يفصل الشرح العربي عن الحسابات الطويلة.
- لا يكدس عدة معادلات في سطر واحد.

قبل إرسال الجواب تحقق من الآتي:

1. هل JSON صالح؟
2. هل كل أوامر LaTeX داخل JSON تستعمل \\؟
3. هل حقول math خالية من النص العربي؟
4. هل لا توجد $ أو $$؟
5. هل توجد مسافة قبل وبعد كل \( ... \) داخل النص؟
6. هل كل خطوة قصيرة وواضحة؟
7. هل الحسابات الطويلة مقسمة إلى calculation_lines؟

==================================================
بيانات التمرين
==================================================

__EXERCISE_JSON__
"""

        return prompt_template.replace(
            "__EXERCISE_JSON__",
            exercise_json,
        ).strip()

    # =========================================================
    # GENERATE
    # =========================================================

    def generate(self, exercise_id: str):
        try:
            exercise = (
                Question.objects
                .select_related("axis")
                .get(
                    id=exercise_id,
                    item_type="bac_question",
                )
            )
        except Question.DoesNotExist:
            return None

        prompt = self.build_prompt(exercise)

        context = BuiltContext(
            question=exercise.content,
            intent="solve_bac_exercise",
            context_text=prompt,
            items=[exercise],
        )

        generated = self.generator.generate(context)

        extracted_answer = self.extract_json(
            generated.answer
        )

        if "raw_answer" in extracted_answer:
            return {
                "mode": "solve_bac_exercise",
                "exercise_id": str(exercise.id),
                "model": generated.model,
                "success": False,
                "error": "invalid_ai_json",
                "raw_answer": extracted_answer["raw_answer"],
                "answer": None,
            }

        normalized_answer = self.normalize_answer(
            extracted_answer,
            exercise,
        )

        return {
            "mode": "solve_bac_exercise",
            "exercise_id": str(exercise.id),
            "model": generated.model,
            "success": True,
            "answer": normalized_answer,
        }


import os
import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()


from knowledge.tutor.orchestrator import TutorOrchestrator

tutor = TutorOrchestrator()

# -----------------------------------
# الرسالة الأولى
# -----------------------------------

response1 = tutor.handle(
    question="اشرح درسة متتاليتان متجاورتان",
    chapter_code="base",
)

print("=" * 80)
print("Session :", response1.session_id)
print("Mode    :", response1.mode)
print("Intent  :", response1.intent)
print("Axis    :", response1.axis_tag)
print("Title   :", response1.axis_title)
print("=" * 80)
print(response1.answer)
#
#
# # -----------------------------------
# # الرسالة الثانية (نفس Session)
# # -----------------------------------
#
# response2 = tutor.handle(
#     question="ما اسم الدرس الذي كنت تشرحه؟ أجب باسم الدرس فقط.",
#     session_id=response1.session_id,
#     chapter_code="base",
# )
#
# print("=" * 80)
# print("Mode    :", response2.mode)
# print("Intent  :", response2.intent)
# print("Axis    :", response2.axis_tag)
# print("=" * 80)
# print(response2.answer)
#
#
# # -----------------------------------
# # الرسالة الثالثة
# # -----------------------------------
#
# response3 = tutor.handle(
#     question="أعطني تمرين بكالوريا حول هذا الدرس.",
#     session_id=response1.session_id,
#     chapter_code="base",
# )
#
# print("=" * 80)
# print("Mode    :", response3.mode)
# print("Intent  :", response3.intent)
# print("=" * 80)
# print(response3.answer)
#
#
# # -----------------------------------
# # الرسالة الرابعة
# # -----------------------------------
#
# response4 = tutor.handle(
#     question="أعطني تلميح فقط ولا تعط الحل.",
#     session_id=response1.session_id,
#     chapter_code="base",
# )
#
# print("=" * 80)
# print(response4.answer)
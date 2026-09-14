from django.test import SimpleTestCase

from adaptive_assessment.services.idea_explorer import IdeaExplorerService
from adaptive_assessment.services.question_validator import QuestionValidator


class VisualQuestionValidatorTests(SimpleTestCase):
    def base_payload(self):
        return {
            "statement_blocks": [
                {"type": "text", "value": "ادرس تغيرات الدالة ثم استنتج النتيجة المطلوبة."},
                {"type": "math", "value": "f(x)=x^2-2x"},
            ],
            "answer_type": "multi_step",
            "correct_answer_latex": "x=1",
            "solution_steps": ["f'(x)=2x-2", "f'(x)=0\\iff x=1"],
            "visuals": [],
            "grading_rubric": {"max_score": 1.0, "required_elements": ["اشتقاق الدالة"]},
            "teacher_hint": "ابدأ بحساب المشتقة.",
            "source_type": "bac",
            "bac_idea_code": "B1",
            "variant_code": "",
            "skill_code": "",
            "difficulty": 2,
            "target_skill_idea_codes": [],
            "requires_external_data": False,
            "ambiguous": False,
        }

    def slot(self):
        return {
            "source_type": "bac",
            "bac_idea_code": "B1",
            "variant_code": "",
            "skill_code": "",
            "difficulty": 2,
            "target_skill_idea_codes": [],
        }

    def test_accepts_valid_function_graph(self):
        payload = self.base_payload()
        payload["visuals"] = [
            {
                "id": "g1",
                "placement": "question",
                "after_step": 0,
                "kind": "function_graph",
                "title": "المنحنى",
                "caption": "تمثيل تقريبي للدالة",
                "x_min": -2,
                "x_max": 4,
                "y_min": -2,
                "y_max": 8,
                "x_label": "x",
                "y_label": "y",
                "series": [{"label": "Cf", "points": [[-2, 8], [0, 0], [1, -1], [2, 0], [4, 8]]}],
                "columns": [],
                "rows": [],
                "commands": [],
            }
        ]
        report = QuestionValidator().validate(payload, slot=self.slot())
        self.assertTrue(report.valid, report.errors)

    def test_rejects_bad_table_shape(self):
        payload = self.base_payload()
        payload["visuals"] = [
            {
                "id": "t1",
                "placement": "solution",
                "after_step": 1,
                "kind": "variation_table",
                "title": "جدول التغيرات",
                "caption": "",
                "x_min": 0,
                "x_max": 0,
                "y_min": 0,
                "y_max": 0,
                "x_label": "",
                "y_label": "",
                "series": [],
                "columns": ["-∞", "1", "+∞"],
                "rows": [{"label": "f", "cells": ["↘", "-1"]}],
                "commands": [],
            }
        ]
        report = QuestionValidator().validate(payload, slot=self.slot())
        self.assertFalse(report.valid)
        self.assertTrue(any("cells must match" in error for error in report.errors))

    def test_rejects_external_or_script_commands(self):
        payload = self.base_payload()
        payload["visuals"] = [
            {
                "id": "d1",
                "placement": "question",
                "after_step": 0,
                "kind": "diagram",
                "title": "شكل",
                "caption": "",
                "x_min": 0,
                "x_max": 0,
                "y_min": 0,
                "y_max": 0,
                "x_label": "",
                "y_label": "",
                "series": [],
                "columns": [],
                "rows": [],
                "commands": ["text 20 20 https://example.com"],
            }
        ]
        report = QuestionValidator().validate(payload, slot=self.slot())
        self.assertFalse(report.valid)


class IdeaExplorerUtilityTests(SimpleTestCase):
    def test_years_are_unique_and_descending(self):
        service = IdeaExplorerService()
        self.assertEqual(service._clean_years([2022, "2024", 2022, "خاص"]), [2024, 2022, "خاص"])

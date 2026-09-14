from django.test import SimpleTestCase

from adaptive_assessment.services.question_validator import QuestionValidator


class DummySource:
    generation_guidance = {
        "forbidden_concepts": ["حساب النهاية"],
    }


class QuestionValidatorTests(SimpleTestCase):
    def test_valid_question(self):
        slot = {
            "source_type": "bac",
            "difficulty": 2,
            "bac_idea_code": "SEQ_DEF_BAC_01",
            "variant_code": "first_order_autonomous",
        }
        payload = {
            "statement": "لتكن المتتالية معرفة بـ u_0=2 و u_{n+1}=u_n+3. احسب u_1 وu_2.",
            "answer_type": "short_text",
            "correct_answer": "u_1=5, u_2=8",
            "solution": "u_1=2+3=5 ثم u_2=5+3=8.",
            "grading_rubric": {
                "max_score": 1.0,
                "required_elements": ["u_1", "u_2"],
            },
            "difficulty": 2,
            "source_type": "bac",
            "bac_idea_code": "SEQ_DEF_BAC_01",
            "variant_code": "first_order_autonomous",
            "requires_external_data": False,
            "ambiguous": False,
        }

        result = QuestionValidator().validate(
            payload,
            slot=slot,
            source=DummySource(),
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_forbidden_concept_is_rejected(self):
        slot = {
            "source_type": "bac",
            "difficulty": 2,
            "bac_idea_code": "SEQ_DEF_BAC_01",
            "variant_code": "",
        }
        payload = {
            "statement": "لتكن متتالية معرفة تراجعيا ثم قم بحساب النهاية لهذه المتتالية.",
            "answer_type": "short_text",
            "correct_answer": "0",
            "solution": "حل كاف للاختبار.",
            "grading_rubric": {"max_score": 1.0, "required_elements": []},
            "difficulty": 2,
            "source_type": "bac",
            "bac_idea_code": "SEQ_DEF_BAC_01",
            "requires_external_data": False,
            "ambiguous": False,
        }
        result = QuestionValidator().validate(
            payload,
            slot=slot,
            source=DummySource(),
        )
        self.assertFalse(result.valid)

# knowledge/services/base_tutor_service.py

from knowledge.retrieval.answer_generator import (
    AnswerGenerator,
    GeneratedAnswer,
)
from knowledge.retrieval.context_builder import BuiltContext


class BaseTutorService:
    mode = "explanation"

    def __init__(self):
        self.generator = AnswerGenerator()

    def generate(
        self,
        context: BuiltContext,
    ) -> GeneratedAnswer:
        return self.generator.generate(
            context_text=context.context_text,
            mode=self.mode,
        )
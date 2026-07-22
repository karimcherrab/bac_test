# knowledge/retrieval/pipeline.py

from dataclasses import dataclass

from knowledge.retrieval.intent_classifier import (
    IntentClassifier,
    IntentResult,
)
from knowledge.retrieval.chapter_retriever import (
    ChapterRetriever,
    ChapterRetrieveResult,
)
from knowledge.retrieval.context_builder import (
    ContextBuilder,
    BuiltContext,
)


@dataclass
class RetrievalPipelineResult:
    question: str
    intent: IntentResult
    retrieval: ChapterRetrieveResult
    context: BuiltContext


class RetrievalPipeline:
    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.chapter_retriever = ChapterRetriever()
        self.context_builder = ContextBuilder()

    def run(
        self,
        question: str,
        chapter_id: int,
    ) -> RetrievalPipelineResult:

        clean_question = question.strip()

        if not clean_question:
            raise ValueError(
                "La question de l'étudiant est vide."
            )

        intent = self.intent_classifier.classify(
            clean_question
        )

        retrieval = self.chapter_retriever.retrieve(
            chapter_id=chapter_id,
            question=clean_question,
            exercises_limit=3,
        )

        context = self.context_builder.build(
            question=clean_question,
            intent=intent.intent,
            retrieval=retrieval,
        )

        return RetrievalPipelineResult(
            question=clean_question,
            intent=intent,
            retrieval=retrieval,
            context=context,
        )
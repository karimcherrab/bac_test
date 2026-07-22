# knowledge/retrieval/intent_classifier.py

from dataclasses import dataclass


@dataclass
class IntentResult:
    intent: str
    confidence: float
    reason: str


class IntentClassifier:
    ALLOWED_INTENTS = {
        "definition",
        "formula",
        "method",
        "skill",
        "hint",
        "example",
        "bac_question",
        "exercise",
        "correction",
        "recommendation",
        "general",
    }

    def classify(self, question: str) -> IntentResult:
        q = question.strip().lower()

        if self._contains(q, [
            "تلميح",
            "ساعدني",
            "عاونني",
            "لا تعطيني الحل",
            "بدون حل",
            "indice",
            "hint",
            "aide",
        ]):
            return IntentResult(
                intent="hint",
                confidence=0.95,
                reason="الطالب طلب تلميحًا دون الحل الكامل.",
            )

        if self._contains(q, [
            "صحح",
            "تصحيح",
            "حلي",
            "حلّي",
            "راجع حلي",
            "corrige",
            "correction",
        ]):
            return IntentResult(
                intent="correction",
                confidence=0.95,
                reason="الطالب يريد تصحيح محاولته.",
            )

        if self._contains(q, [
            "اعطني تمرين",
            "أعطني تمرين",
            "تمرين جديد",
            "اختبرني",
            "exercice",
            "exercise",
        ]):
            return IntentResult(
                intent="exercise",
                confidence=0.95,
                reason="الطالب طلب تمرينًا جديدًا.",
            )

        if self._contains(q, [
            "بكالوريا",
            "موضوع باك",
            "تمرين باك",
            "bac",
        ]):
            return IntentResult(
                intent="bac_question",
                confidence=0.90,
                reason="الطالب طلب محتوى متعلقًا بالبكالوريا.",
            )

        if self._contains(q, [
            "ماذا أراجع",
            "وش نراجع",
            "خطة مراجعة",
            "نصيحة",
            "recommend",
        ]):
            return IntentResult(
                intent="recommendation",
                confidence=0.90,
                reason="الطالب يريد توصية للمراجعة.",
            )

        if self._contains(q, [
            "ما هو",
            "ما هي",
            "تعريف",
            "ماذا يعني",
            "عرف",
        ]):
            return IntentResult(
                intent="definition",
                confidence=0.90,
                reason="الطالب يطلب تعريفًا أو معنى.",
            )

        if self._contains(q, [
            "قانون",
            "صيغة",
            "علاقة",
            "formula",
        ]):
            return IntentResult(
                intent="formula",
                confidence=0.90,
                reason="الطالب يطلب قانونًا أو صيغة.",
            )

        if self._contains(q, [
            "كيف",
            "طريقة",
            "أثبت",
            "اثبت",
            "برهن",
            "نبرهن",
        ]):
            return IntentResult(
                intent="method",
                confidence=0.80,
                reason="الطالب يطلب طريقة أو برهانًا.",
            )

        if self._contains(q, [
            "مثال",
            "اعطني مثال",
            "أعطني مثال",
        ]):
            return IntentResult(
                intent="example",
                confidence=0.90,
                reason="الطالب يطلب مثالًا.",
            )

        return IntentResult(
            intent="general",
            confidence=0.60,
            reason="سؤال تعليمي عام.",
        )

    @staticmethod
    def _contains(text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)
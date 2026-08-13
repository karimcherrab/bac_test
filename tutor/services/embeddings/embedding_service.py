

class EmbeddingService:
    """
    Service responsable de la génération des embeddings.
    """

    MODEL_NAME = "BAAI/bge-m3"

    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            from sentence_transformers import SentenceTransformer

            cls._model = SentenceTransformer(
                cls.MODEL_NAME,
                device="cpu",
            )

        return cls._model

    @classmethod
    def encode(cls, text: str) -> list[float]:
        if not text or not text.strip():
            return []

        model = cls.get_model()

        embedding = model.encode(
            text.strip(),
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return embedding.tolist()
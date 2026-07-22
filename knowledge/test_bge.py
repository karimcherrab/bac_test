from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

model = SentenceTransformer("BAAI/bge-m3")

texts = [
    "إثبات الرتابة",
    "المتتالية متزايدة",
    "الاحتمالات",
]

embeddings = model.encode(
    texts,
    normalize_embeddings=True
)

print(cos_sim(embeddings[0], embeddings[1]))
print(cos_sim(embeddings[0], embeddings[2]))
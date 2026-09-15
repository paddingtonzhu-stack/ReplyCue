"""Embedding providers used by the SQLite-backed retrieval index."""
from hashlib import blake2b
import math
import re
from typing import Protocol

from openai import OpenAI


class EmbeddingProvider(Protocol):
    name: str
    dimensions: int
    def embed(self, text: str) -> list[float]: ...


class DevelopmentEmbedding:
    name = 'development-feature-hash-v1'
    dimensions = 128

    def embed(self, text):
        vector = [0.0] * self.dimensions
        for token in re.findall(r'\w+|[^\w\s]', text.casefold()):
            digest = blake2b(token.encode('utf-8'), digest_size=8).digest()
            vector[int.from_bytes(digest[:4], 'big') % self.dimensions] += 1 if digest[4] & 1 else -1
        length = math.sqrt(sum(v*v for v in vector)) or 1
        return [v / length for v in vector]


class OpenAIEmbedding:
    def __init__(self, api_key: str, model: str = 'text-embedding-3-small', dimensions: int = 512):
        self.model = model
        self.dimensions = dimensions
        self.name = f'openai:{model}'
        self.client = OpenAI(api_key=api_key)

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,
            encoding_format='float',
        )
        return response.data[0].embedding


def cosine(left, right):
    denom = math.sqrt(sum(v*v for v in left) * sum(v*v for v in right))
    return sum(a*b for a,b in zip(left, right)) / denom if denom else 0.0

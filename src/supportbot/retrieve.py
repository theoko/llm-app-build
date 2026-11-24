"""Episode 1: keyword retrieval with BM25. No embeddings yet."""
import math
import re
from collections import Counter

from .corpus import Chunk

TOKEN = re.compile(r"[a-z0-9_]+")


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


class BM25:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks, self.k1, self.b = chunks, k1, b
        self.tf = [Counter(tokens(f"{c.heading} {c.text}")) for c in chunks]
        self.len = [sum(t.values()) for t in self.tf]
        self.avg = sum(self.len) / len(self.len)
        df = Counter(w for t in self.tf for w in t)
        n = len(chunks)
        self.idf = {w: math.log(1 + (n - d + 0.5) / (d + 0.5)) for w, d in df.items()}

    def search(self, query: str, k: int = 5) -> list[tuple[Chunk, float]]:
        q = tokens(query)
        scores = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            for w in q:
                f = tf.get(w)
                if f:
                    norm = f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg)
                    s += self.idf[w] * f * (self.k1 + 1) / norm
            if s > 0:
                scores.append((s, i))
        scores.sort(reverse=True)
        return [(self.chunks[i], s) for s, i in scores[:k]]

"""Small deterministic JavaScript token TF-IDF reference encoder.

This is lexical feature extraction, not a JavaScript parser or taint analysis.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

import numpy as np

TOKEN = re.compile(r'''(?P<string>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)|(?P<id>[A-Za-z_$][\w$]*)|(?P<number>\d+(?:\.\d+)?)|(?P<op>===|!==|=>|==|!=|&&|\|\||\?\.|[^\s])''')


def tokenize(code: str) -> list[str]:
    result = []
    for match in TOKEN.finditer(code):
        if match.lastgroup == "comment":
            continue
        if match.lastgroup == "string":
            # Preserve interpolation markers because they can affect code semantics.
            result.append("<template>" if match.group().startswith("`") else "<string>")
        elif match.lastgroup == "number":
            result.append("<number>")
        else:
            result.append(match.group())
    return result


def terms(code: str) -> list[str]:
    t = tokenize(code)
    return t + [a+"\x1f"+b for a, b in zip(t, t[1:])]


@dataclass
class Vectorizer:
    vocabulary: dict[str, int]
    idf: np.ndarray

    @classmethod
    def fit(cls, codes: list[str], max_features: int = 1600) -> "Vectorizer":
        if not codes or not 1 <= max_features <= 10000:
            raise ValueError("Cannot fit an empty corpus")
        count: Counter = Counter()
        for code in codes:
            count.update(set(terms(code)))
        selected = sorted(count, key=lambda k: (-count[k], k))[:max_features]
        if not selected:
            raise ValueError("Training code contains no lexical features")
        vocabulary = {word: i for i, word in enumerate(sorted(selected))}
        idf = np.array([np.log((1+len(codes))/(1+count[word]))+1 for word in vocabulary], dtype=float)
        return cls(vocabulary, idf)

    def transform(self, codes: list[str]) -> np.ndarray:
        x = np.zeros((len(codes), len(self.vocabulary)), dtype=float)
        for i, code in enumerate(codes):
            for token, count in Counter(terms(code)).items():
                if token in self.vocabulary:
                    x[i, self.vocabulary[token]] = 1+np.log(count)
        x *= self.idf
        norms = np.linalg.norm(x, axis=1, keepdims=True)
        return x / np.maximum(norms, 1e-12)

    def to_dict(self) -> dict:
        return {"vocabulary": self.vocabulary, "idf": self.idf.tolist(), "tokenizer": "js-lexical-v1"}

    @classmethod
    def from_dict(cls, obj: dict) -> "Vectorizer":
        if obj.get("tokenizer") != "js-lexical-v1":
            raise ValueError("Unsupported tokenizer version")
        vocabulary, idf = obj["vocabulary"], np.asarray(obj["idf"], dtype=float)
        if not isinstance(vocabulary, dict) or len(vocabulary) > 10000 or sorted(vocabulary.values()) != list(range(len(vocabulary))):
            raise ValueError("Invalid vocabulary")
        if idf.shape != (len(vocabulary),) or not np.isfinite(idf).all():
            raise ValueError("Invalid IDF vector")
        return cls(vocabulary, idf)

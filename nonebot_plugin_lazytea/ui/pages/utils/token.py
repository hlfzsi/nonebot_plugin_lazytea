from typing import List


def get_ngrams(sentence: str, n: int = 2) -> List[str]:
    if len(sentence) < n:
        return [sentence] if sentence else []
    return [sentence[i:i+n] for i in range(len(sentence) - n + 1)]

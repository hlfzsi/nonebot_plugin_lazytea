"""为保证低内存占用, 此处只能使用此类方式进行预处理"""
import re
from typing import List

TOKEN_RE_WITH_PUNCT = re.compile(
    r'[\u4e00-\u9fa5]+|[a-zA-Z]+|\d+|[^\s\u4e00-\u9fa5a-zA-Z\d]+')


def tokenize(sentence: str) -> List[str]:
    if not sentence:
        return []

    initial_tokens = TOKEN_RE_WITH_PUNCT.findall(sentence)

    final_tokens = []
    for token in initial_tokens:
        if '\u4e00' <= token[0] <= '\u9fa5':
            if len(token) > 1:
                for i in range(len(token) - 1):
                    final_tokens.append(token[i:i+2])
            else:
                final_tokens.append(token)

        elif 'a' <= token[0].lower() <= 'z':
            final_tokens.append(token.lower())
        else:
            final_tokens.append(token)

    return final_tokens

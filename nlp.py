from collections import defaultdict
import numpy as np


def match_all_3grams_from_list(L: list[str]) -> defaultdict[str, set[str]]:
    trigrams = defaultdict(set)
    for elem in L:
        for i in range(max(0, 1 + len(elem) - 3)):
            trigrams[elem[i : i + 3]].add(elem)
    return trigrams


def get_all_3grams_from_string(s: str) -> list[str]:
    return [s[i : i + 3] for i in range(max(0, 1 + len(s) - 3))]


def idf_score(corpus: list, subcorpus: list) -> float:
    return 1 + np.log((1 + len(corpus)) / (1 + len(subcorpus)))

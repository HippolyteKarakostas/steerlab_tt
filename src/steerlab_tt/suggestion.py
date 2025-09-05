from scipy.sparse import csr_matrix
from typing import Iterable
import numpy as np

from steerlab_tt.nlp import get_all_3grams_from_string


def get_all_sequences_weights(
    idfs: dict[str, float], sequence_index_matching: dict[str, int], sequence_trigram_index_matching: dict[str, int]
) -> csr_matrix:
    data, rows, cols = [], [], []
    for title, i in sequence_index_matching.items():
        trigrams = get_all_3grams_from_string(title)
        for trigram in trigrams:
            j = sequence_trigram_index_matching[trigram]
            data.append(idfs[trigram])
            rows.append(i)
            cols.append(j)
    return csr_matrix(
        (data, (rows, cols)),
        shape=(len(sequence_index_matching), len(sequence_trigram_index_matching)),
        dtype="float32",
    )


def norm(L: Iterable) -> float:
    return np.sqrt(sum(x**2 for x in L))


def get_all_posible_choices(trigrams_request: list[str], sequences_by_trigram: dict[str, set]) -> set:
    if not trigrams_request:
        return set()
    return set.intersection(*(sequences_by_trigram.get(trigram, set()) for trigram in trigrams_request))


def get_most_relevant_choices(
    request: str,
    sequences_by_trigram: dict[str, set],
    idfs: dict[str, float],
    weights: csr_matrix,
    indexes: dict[str, int],
    real_norm_sequence_matching: dict[str, str],
    is_title=True,
) -> str:
    trigrams_request = get_all_3grams_from_string(request)
    posible_choices = get_all_posible_choices(trigrams_request, sequences_by_trigram) | set.intersection(
        *(
            get_all_posible_choices(get_all_3grams_from_string(subrequest), sequences_by_trigram)
            for subrequest in request.split(" ")
        )
    )
    w_q = np.array([idfs[trigram] if trigram in trigrams_request else 0 for trigram in idfs])
    choices_and_scores = [("", 0) for rank in range(5)]
    for choice in posible_choices:
        w_d = weights[indexes[choice]]
        score = float(w_d @ w_q) / norm(w_q) / np.sqrt(w_d.multiply(w_d).sum())
        put_choice_on_right_place(choice, score, choices_and_scores)
    return [
        {("title" if is_title else "author"): real_norm_sequence_matching.get(choice[0], "")}
        for choice in choices_and_scores
    ]


def put_choice_on_right_place(choice, score, choices_and_scores):
    for rank in range(5):
        if score > choices_and_scores[rank][1]:
            for other_rank in range(4, rank, -1):
                choices_and_scores[other_rank] = choices_and_scores[other_rank - 1]
            choices_and_scores[rank] = (choice, score)
            break

"""
Utilitaires pour la route /suggest de l'app.

Ce module fournit des fonctions qui implémentent toute la logique algorithmique
pour l'autocomplétion et la suggestion des titres.
"""


from scipy.sparse import csr_matrix
from typing import Iterable
import numpy as np
import re
import pandas as pd

from steerlab_tt.nlp import get_all_3grams_from_string


def get_all_sequences_weights(
    idfs: dict[str, float], sequence_index_matching: dict[str, int], sequence_trigram_index_matching: dict[str, int]
) -> csr_matrix:
    """Construit la matrice parcimonieuse des poids (séquence * trigramme).

    Chaque séquence (titre/auteur) est représentée par un vecteur dont les
    composantes sont les IDF des trigrammes qu’elle contient.
    Pour chaque séquence d'indice i, pour chaque trigram d'indice j,
    la case (i, j) de la matrice contient le score IDF du trigram j dans la séquence i.

    Args:
        idfs: Mapping trigramme -> poids IDF.
        sequence_index_matching: Mapping séquence normalisée -> ligne de la matrice.
        sequence_trigram_index_matching: Mapping trigramme -> colonne de la matrice.

    Returns:
        csr_matrix: Matrice (n_sequences * n_trigrammes), dtype float32.
    """
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


def _norm(L: Iterable) -> float:
    return np.sqrt(sum(x**2 for x in L))


def get_all_possible_choices(trigrams_request: list[str], sequences_by_trigram: dict[str, set]) -> set:
    """Retourne l’ensemble des séquences qui contiennent tous les trigrammes requis.

    Args:
        trigrams_request: Trigrammes de la requête (éventuellement vide).
        sequences_by_trigram: Mapping {trigramme: {ensemble de séquences qui le contiennent}}.

    Returns:
        set[str]: Séquences candidates (intersection des ensembles).
    """
    if not trigrams_request:
        return set()
    trigrams = sorted(trigrams_request, key=lambda trigram: len(sequences_by_trigram.get(trigram, set())))
    all_possible_choices = sequences_by_trigram.get(trigrams[0], set()).copy()
    for trigram in trigrams[1:]:
        if not all_possible_choices:
            break
        all_possible_choices &= sequences_by_trigram.get(trigram, set())
    return all_possible_choices


def get_most_relevant_choices(
    request: str,
    sequences_by_trigram: dict[str, set],
    idfs: dict[str, float],
    weights: csr_matrix,
    weights_norms: list[float],
    indexes: dict[str, int],
    real_norm_sequence_matching: dict[str, str],
    is_title: bool = True,
) -> str:
    """Retourne les 5 séquences les plus pertinentes pour une requête.

    Calcule un score type IDF: produit scalaire w_d @ w_q normalisé.

    Stratégie:
      1) Génère les trigrammes de la requête.
      2) Restreint l’espace de recherche aux séquences contenant:
         - tous les trigrammes de la requête, OU
         - l’intersection par mot (pour couvrir les multi-mots et géré l'ordre).
      3) Score = (w_d @ w_q) / (||w_q|| * ||w_d||), avec w_d issu de la matrice CSR.

    Args:
        request: Requête normalisée (ex. titre en minuscules sans accents).
        sequences_by_trigram: trigram -> set des séquences contenant ce trigramme.
        idfs: trigram -> poids IDF.
        weights: Matrice CSR (séquence x trigram) des poids.
        weights_norms: norme euclidienne de chaque ligne de weights
        indexes: séquence -> index de ligne dans `weights`.
        real_norm_sequence_matching: séquence normalisée -> séquence affichable.
        is_title: Si True, renvoie {"title": ...}, sinon {"author": ...}.

    Returns:
        list[dict]: Top-5 sous forme de dicts prêts à être sérialisés.
    """
    trigrams_request = get_all_3grams_from_string(request)
    posible_choices = get_all_possible_choices(trigrams_request, sequences_by_trigram) | set.intersection(
        *(
            get_all_possible_choices(get_all_3grams_from_string(subrequest), sequences_by_trigram)
            for subrequest in request.split(" ")
        )
    )
    w_q = np.array([idfs[trigram] if trigram in trigrams_request else 0 for trigram in idfs])
    choices_and_scores = [("", 0) for rank in range(5)]
    for choice in posible_choices:
        w_d = weights[indexes[choice]]
        norm = weights_norms[indexes[choice]]
        score = float(w_d @ w_q) / _norm(w_q) / norm
        # Placer le nouveau choice à la bonne place dans (ou dehors) le top-5 courant des choix
        _put_choice_on_right_place(choice, score, choices_and_scores)
    return [
        {("title" if is_title else "author"): real_norm_sequence_matching.get(choice[0], "")}
        for choice in choices_and_scores
    ]


def _put_choice_on_right_place(choice: str, score: float, choices_and_scores: dict[int, tuple[str, float]]) -> None:
    for rank in range(5):
        if score > choices_and_scores[rank][1]:
            for other_rank in range(4, rank, -1):
                choices_and_scores[other_rank] = choices_and_scores[other_rank - 1]
            choices_and_scores[rank] = (choice, score)
            break


def get_most_relevant_choices_from_regexp(regexp: str, df: pd.DataFrame, real_titles: list[str]) -> list:
    """Retourne jusqu’à 5 titres correspondant à une expression régulière.

    Args:
        regexp: Expression régulière (Python). Si invalide, retourne [].
        df: DataFrame catalogue (doit contenir la colonne "Title").
        real_titles: Liste des titres (valeurs exactes) à considérer.

    Returns:
        list[dict[str, str]]: Liste de dicts {"title": ...} (au plus 5 éléments).
    """
    try:
        pattern = re.compile(regexp)
    except re.error:
        return []
    return [
        {"title": title}
        for title in df[
            df["Title"].isin([real_title for real_title in real_titles if pattern.search(real_title) is not None])
        ]["Title"]
        .drop_duplicates()
        .iloc[:5]
    ]

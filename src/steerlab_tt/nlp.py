"""
Utilitaires de traitement de texte basés sur les trigrammes.

Ce module fournit des fonctions pour extraire des trigrammes à partir de chaînes
ou de listes, et pour calculer un score IDF (inverse document frequency).
Ces fonctions servent de briques de base aux suggestions de titres/auteurs.
"""


from collections import defaultdict
import numpy as np


def match_all_3grams_from_list(L: list[str]) -> defaultdict[str, set[str]]:
    """Construit l'index de tous les trigrammes présents dans une liste de chaînes.

    Args:
        L: Liste de chaînes normalisées.

    Returns:
        defaultdict: mapping {trigramme : {ensemble de chaînes (titres ou auteurs) contenant ce trigramme}}.
    """
    trigrams = defaultdict(set)
    for elem in L:
        for i in range(max(0, 1 + len(elem) - 3)):
            trigrams[elem[i : i + 3]].add(elem)
    return trigrams


def get_all_3grams_from_string(s: str) -> list[str]:
    """Retourne tous les trigrammes présents dans une chaîne."""
    return [s[i : i + 3] for i in range(max(0, 1 + len(s) - 3))]


def idf_score(corpus: list, subcorpus: list) -> float:
    """Calcule un IDF lissé: 1 + ln((1 + |corpus|) / (1 + |subcorpus|)).

    Conceptuellement, le score IDF d'un trigramme parmi un ensemble de séquences (corpus)
    peut se définir comme l'inverse de la proportion des séquences du corpus qui
    contiennent ce trigramme, parmi l'ensemble du corpus: donc |corpus| / |subcorpus|.
    On choisit de définir une version lissée de l'IDF qui
    - gère le cas où le subcorpus est nul
    - tempère le score des trigrammes très rares (gestion de la sensibilité au bruit)
    - diminue la discrimination entre les trigrammes (échelle logarithmique)

    Args:
        corpus: Liste de (toutes les) séquences
        subcorpus: Liste des séquences qui vérifient une propriété (ici celle de contenir un trigramme)

    Returns:
        score IDF du subcorpus au sein du corpus
    """
    return 1 + np.log((1 + len(corpus)) / (1 + len(subcorpus)))

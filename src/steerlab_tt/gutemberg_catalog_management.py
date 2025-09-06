"""
Gestion du catalogue Gutenberg.

Fonctions principales :
    - Téléchargement du catalogue officiel (CSV).
    - Nettoyage et normalisation des titres et auteurs.
    - Construction d'un DataFrame enrichi (titres/auteurs normalisés).

Les données sont stockées dans un dossier `data/` à côté du module.
"""


import requests
import string
import unicodedata
import re
import pandas as pd
from pathlib import Path

# caractères à garder tels quels
_KEEP = set("-'")  # utile pour noms composés et titres
_TRANS_TABLE = str.maketrans({c: " " for c in string.punctuation if c not in _KEEP})
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def download_catalog() -> Path:
    """Télécharge le catalogue Gutenberg et l’enregistre en cache local.

    Returns:
        Path: Chemin absolu du fichier CSV téléchargé.
    Raises:
        requests.HTTPError: Si le téléchargement échoue.
    """
    url = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"
    r = requests.get(url)
    csv_path = DATA_DIR / "pg_catalog.csv"
    with open(csv_path, "wb") as f:
        f.write(r.content)
    return csv_path


def remove_accents(s: str) -> str:
    """
    La normalisation NFKD (Normalization Form KD = Compatibility Decomposition) décompose les caractères en leur forme de base + diacritiques.
    Par exemple:
        "e" --> "e"
        "è" --> "e`"
    La fonction 'unicodedata.normalize' opère cette séparation
    La fonction 'unicodedata.combining' remplace chaque caractère par un entier différent de 0 si c'est un accent, 0 si c'est un accent.
    """
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def base_normalize(s: str) -> str:
    """Normalise une chaîne :
    - minuscule
    - accents supprimés
    - ponctuation remplacée par des espaces (sauf - et ')
    - espaces multiples compactés
    """
    if not s:
        return ""
    # suppression de la casse
    s = s.casefold()
    s = remove_accents(s)
    s = s.translate(_TRANS_TABLE)  # ponctuation → espaces (sauf - et ')
    # compacter les espaces multiples et supprimer les espaces en début et fin de chaine
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_title(title: str) -> dict:
    """wrapper sur base_normalize (pour plus de clarté dans le fichier principal)"""
    # À enrichir si on veut aller plus loin, par exemple supprimer les articles
    norm = base_normalize(title)
    return norm


def normalize_authors(authors: str) -> list:
    """split et normalise chaque auteur"""
    if not authors:
        return []
    return sorted(set(normalize_author(author) for author in authors.split(";")))


def _check_initials(potential_initials: str, potential_full_name: str) -> bool:
    initials = [initial for initial in potential_initials.split(" ") if initial]
    names = [name for name in potential_full_name.split(" ") if name]
    if len(initials) == len(names):
        for initial, name in zip(initials, names):
            if initial[0] != name[0]:
                return False
        return True
    return False


def _remove_all_potential_initials(s: str) -> str:
    all_potential_initials = re.findall(r"((?:(?:\w+ )|(?:\w\. ))+)\(((?:\w+ ?)+?)\)", s)
    if all_potential_initials:
        for potential_initials, potential_full_name in all_potential_initials:
            if _check_initials(potential_initials, potential_full_name):
                s = s.replace(potential_initials, potential_full_name)
    return s


def normalize_author(author: str) -> str:
    """
    Nettoie les auteurs pour l'autocomplete

    Étapes:
      - supprime dates (chiffres), contenus entre ()/[]/{}
      - compresse initiales 'J. K.' → 'jk'
      - garde - et ' pour les noms composés (dumas, o'connor)
      - normalisation de base (casse, accents, ponctuation)
      - supprime tirets résiduels et espaces multiples
    """
    if not author:
        return ""
    s = author
    s = _remove_all_potential_initials(s)
    # retirer parenthèses / crochets / accolades et leur contenu
    s = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", s)
    # retirer chiffres (dates, numéros)
    s = re.sub(r"\d+", " ", s)
    # normalisation de base (accents, casse, ponctuation)
    s = base_normalize(s)
    # compacter initiales restantes qui n'ont pas pu être supprimées: "j. k." -> "jk"; "j k" -> "jk"
    s = re.sub(r"\b([a-z])\b(?:\s+|\.)", r"\1", s)  # colle les lettres isolées
    # Retirer les tirets résiduels en début et fin de chaine
    s = re.sub(r"^-*", "", s)
    s = re.sub(r"-*$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def get_and_preprocess_catalog() -> pd.DataFrame:
    """Télécharge et prétraite le catalogue Gutenberg.

    Ajoute au DataFrame :
      - title_norm : titre normalisé
      - auths_norm : liste d'auteurs normalisés
      - auth_norm  : auteurs concaténés (string)

    Returns:
        pd.DataFrame: catalogue enrichi.
    """
    csv_path = download_catalog()
    df = pd.read_csv(csv_path).fillna("")
    df["Title"] = df["Title"].apply(lambda s: re.sub(r"\n", " ", s))
    df["title_norm"] = df["Title"].apply(lambda s: normalize_title(s))
    df["auths_norm"] = df["Authors"].apply(lambda s: normalize_authors(s))
    df["auth_norm"] = df["auths_norm"].apply(lambda s: "; ".join(s))
    return df

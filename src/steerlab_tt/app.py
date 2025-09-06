"""
Application Flask de démonstration pour l'autocomplétion de titres et d'auteurs.

Définit 3 routes principales :
    - GET /               : page d'accueil (template HTML).
    - GET /suggest        : renvoie des suggestions JSON (titres ou auteurs).
    - GET /resolve_title  : résout un titre en URL sur le site gutenberg.org.

Le backend s'appuie sur le catalogue Gutenberg téléchargé et prétraité.
"""


from flask import Flask, request, render_template, jsonify
import logging
import numpy as np

from steerlab_tt.gutemberg_catalog_management import get_and_preprocess_catalog, normalize_title
from steerlab_tt.nlp import match_all_3grams_from_list, idf_score
from steerlab_tt.suggestion import (
    get_all_sequences_weights,
    get_most_relevant_choices,
    get_most_relevant_choices_from_regexp,
)


logger = logging.getLogger(__name__)

app = Flask(__name__)


df = get_and_preprocess_catalog()
title_norm_all = df["title_norm"].drop_duplicates().sort_values().to_list()
auth_norm_all = df["auth_norm"].drop_duplicates().sort_values().to_list()
title_index_matching = {title: index for index, title in enumerate(title_norm_all)}
auth_index_matching = {auth: index for index, auth in enumerate(auth_norm_all)}
real_norm_title_matching = df.set_index("title_norm")["Title"].to_dict()
real_norm_auth_matching = df.set_index("auth_norm")["Authors"].to_dict()
title_3grams = match_all_3grams_from_list(title_norm_all)
auth_3grams = match_all_3grams_from_list(auth_norm_all)
title_trigram_index_matching = {trigram: index for index, trigram in enumerate(title_3grams)}
auth_trigram_index_matching = {trigram: index for index, trigram in enumerate(auth_3grams)}
title_idfs = {trigram: idf_score(title_norm_all, title_3grams.get(trigram, set())) for trigram in title_3grams}
auth_idfs = {trigram: idf_score(auth_norm_all, auth_3grams.get(trigram, set())) for trigram in auth_3grams}
title_weights = get_all_sequences_weights(title_idfs, title_index_matching, title_trigram_index_matching)
title_weights_norms = [np.sqrt(w_d.multiply(w_d).sum()) for w_d in title_weights]
auth_weights = get_all_sequences_weights(auth_idfs, auth_index_matching, auth_trigram_index_matching)
auth_weights_norms = [np.sqrt(w_d.multiply(w_d).sum()) for w_d in auth_weights]
real_title_id_matching = df.set_index("Title")["Text#"].to_dict()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/suggest")
def suggest():
    """Autosuggestions de titres/auteurs.

    Query Params:
        title_query: Chaîne libre pour suggestion de titres.
        auth_query: Chaîne libre pour suggestion d'auteurs.
        mode: "regexp" pour baser les suggestions sur une expression régulière.
    Returns:
        list[dict]: Jusqu'à 5 suggestions. Clefs: {"title": str} ou {"author": str}.
    """
    choices = []
    query = request.args.get("title_query", "")
    mode = request.args.get("mode", "")
    if mode == "regexp":
        return get_most_relevant_choices_from_regexp(query, df, list(real_title_id_matching))
    if query:
        query = normalize_title(query)
        choices = get_most_relevant_choices(
            query,
            title_3grams,
            title_idfs,
            title_weights,
            title_weights_norms,
            title_index_matching,
            real_norm_title_matching,
            is_title=True,
        )
        return choices
    auth_query = request.args.get("auth_query", "")
    if auth_query:
        auth_query = normalize_title(auth_query)
        choices = get_most_relevant_choices(
            auth_query,
            auth_3grams,
            auth_idfs,
            auth_weights,
            auth_weights_norms,
            auth_index_matching,
            real_norm_auth_matching,
            is_title=False,
        )
    return choices


@app.get("/resolve_title")
def resolve_title():
    """Lance une recherche de titre directement sur le site gutemberg.org.

    Lorsque le titre requété est valide, la route renvoie directement vers
    la page dudit livre sur le site gutember.org via l'ID unique du livre.
    Sinon, effectue une recherche sur le site.

    Query Params:
        title_query: Chaîne libre pour suggestion de titres.
    Returns:
        list[dict]: [{"url": str, "message": str}].
    """
    title_query = request.args.get("title_query", "").strip()
    title_id = real_title_id_matching.get(title_query, "")
    if title_id:
        url = f"https://www.gutenberg.org/ebooks/{title_id}"
        return jsonify(ok=True, url=url, message="Bonne lecture !")
    url = f"https://www.gutenberg.org/ebooks/search/?query={title_query}"
    return (
        jsonify(
            ok=False, url=url, message="Aucun livre du projet Gutenberg ne porte ce titre. Vérifiez l'orthographe."
        ),
        404,
    )


def main():
    app.run("0.0.0.0", 5000, debug=False, threaded=True)


if __name__ == "__main__":
    main()

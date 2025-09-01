from flask import Flask, request, render_template
import logging

from gutemberg_catalog_management import get_and_preprocess_catalog, normalize_title
from nlp import match_all_3grams_from_list, idf_score
from suggestion import get_all_sequences_weights, get_most_relevant_choices


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
auth_weights = get_all_sequences_weights(auth_idfs, auth_index_matching, auth_trigram_index_matching)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/suggest")
def suggest():
    title_q = request.args.get("title_q", "")
    if title_q:
        title_q = normalize_title(title_q)
        choices = get_most_relevant_choices(
            title_q,
            title_3grams,
            title_idfs,
            title_weights,
            title_index_matching,
            real_norm_title_matching,
            is_title=True,
        )
        return choices
    auth_q = request.args.get("auth_q", "")
    if auth_q:
        auth_q = normalize_title(auth_q)
        choices = get_most_relevant_choices(
            auth_q, auth_3grams, auth_idfs, auth_weights, auth_index_matching, real_norm_auth_matching, is_title=False
        )
    return choices


if __name__ == "__main__":
    app.run("0.0.0.0", 5000, debug=False, threaded=True)

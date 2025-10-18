from __future__ import annotations

import json
import textwrap

from django.contrib.postgres.search import TrigramSimilarity
from django.db import models


def json_format_with_wrap(item: [] | {} | str | None, width: int = 70) -> str:
    """Formatuje 'ładnie' dane JSON, w sytuacji, gdyby jakas linia
    przekraczała szerokośc ``width``, zawija.
    """
    s = json.dumps(item, indent=2).split("\n")
    news = []
    for elem in s:
        if len(elem) > width:
            elem = textwrap.fill(elem, width=width)
        news.append(elem)
    return "\n".join(news)


def perform_trigram_search(
    queryset,
    trigram_db_field,
    trigram_db_value,
    max_number_records=5,
    minimum_acceptable_similarity=0.6,
    db_trigram_target="podobienstwo",
    similarity_step_down=0.05,
    similarity_step_up=0.01,
    max_steps=20,
    initial_similarity=None,
) -> list[models.Model] | None:
    """Performs a TrigramSimilarity search, starting from similarity value and
    descending/ascending to find the optimal number of records.

    :param queryset: Django queryset, can be anything.
    :param trigram_db_field: trigram database field, can be Lower('db_column') etc,
    :param trigram_db_value: value you're looking for in trigram_db_field, will be used
    to compare similarity.
    :param initial_similarity: Starting similarity value. If None, uses minimum_acceptable_similarity + 0.2
    """

    kwargs_annotate = {
        db_trigram_target: TrigramSimilarity(trigram_db_field, trigram_db_value)
    }

    # Start from a more reasonable similarity value for better performance
    if initial_similarity is None:
        current_similarity = min(minimum_acceptable_similarity + 0.2, 0.8)
    else:
        current_similarity = initial_similarity
    current_step = 0
    while (
        current_similarity > minimum_acceptable_similarity and current_step < max_steps
    ):
        current_step += 1
        kwargs_filter = {db_trigram_target + "__gte": current_similarity}
        my_queryset = (
            queryset.annotate(**kwargs_annotate)
            .filter(**kwargs_filter)
            .order_by(f"-{db_trigram_target}")
        )

        # Use list slicing instead of count() for better performance
        results_list = list(my_queryset[: max_number_records + 1])
        cnt = len(results_list)

        if cnt == max_number_records + 1:
            # Za dużo rekordów. Zwiększ nieznacznie pożądane podobieństwo i szukaj dalej.
            current_similarity += similarity_step_up
            continue

        if cnt == 0:
            # Za mało rekordów. Zmniejsz poszukiwane prawdopodobieństwo:
            current_similarity -= similarity_step_down
            continue

        # Return queryset, not the list
        return my_queryset[:max_number_records]

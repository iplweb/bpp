from __future__ import annotations

import json
import textwrap

from django.db import models

from django.contrib.postgres.search import TrigramSimilarity


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
) -> list[models.Model] | None:
    """Performs a TrigramSimilarity search, starting from similarity value of
    1.0, desceding every ``step`` as long as the number of records is below ``max_number_records``

    :param queryset: Django queryset, can be anything.
    :param trigram_db_field: trigram database field, can be Lower('db_column') etc,
    :param trigram_db_value: value you're looking for in trigram_db_field, will be used
    to compare similarity.
    """

    kwargs_annotate = {
        db_trigram_target: TrigramSimilarity(trigram_db_field, trigram_db_value)
    }

    current_similarity = 1.0
    current_step = 0
    while (
        current_similarity > minimum_acceptable_similarity or current_step >= max_steps
    ):
        current_step += 1
        kwargs_filter = {db_trigram_target + "__gte": current_similarity}
        my_queryset = queryset.annotate(**kwargs_annotate).filter(**kwargs_filter)

        cnt = my_queryset[: max_number_records + 1].count()
        if cnt == max_number_records + 1:
            # Za dużo rekordów. Zwiększ nieznacznie pożądane podobieństwo i szukaj dalej.
            current_similarity += similarity_step_up
            continue

        if cnt == 0:
            # Za mało rekordów. Zmniejsz poszukiwane prawdopodobieństwo:
            current_similarity -= similarity_step_down
            continue

        return my_queryset.order_by(f"-{db_trigram_target}")

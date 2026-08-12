"""Wspólne narzędzia testów e2e migracji ``pbn_api``.

Testy, które puszczają prawdziwy ``MigrationExecutor`` w tył i w przód,
MUSZĄ posprzątać po sobie — inaczej worker testowy zostaje na starej
migracji i psuje wszystkie kolejne testy w tym procesie.
"""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def przywroc_czubek_migracji():
    """Doprowadź bazę workera do NAJNOWSZYCH migracji — WSZYSTKICH aplikacji.

    Dwie rzeczy, które łatwo tu zrobić za wąsko; obie kosztowały przebieg
    suity:

    1. **Czubek grafu, a nie zaszyty numer.** Cofnięcie do stanu „PRZED"
       odapplikowuje wszystko powyżej, więc powrót do stałej zostawia bazę
       o tyle migracji w tyle, ile ich od napisania testu przybyło. Tak
       właśnie było: jeden test e2e wracał na ``0077``, drugi na ``0079``,
       więc dodanie ``0080`` (``SentData.withdrawn_at``, faza 05
       soft-delete) wywróciło Playwrightowy test admina ``SentData``
       błędem ``UndefinedColumn``.

    2. **Wszystkie aplikacje, nie tylko ``pbn_api``.** Migracje innych
       aplikacji zależą od ``pbn_api`` (np.
       ``pbn_integrator/0002_indeks_content_type_object_id`` wymaga
       ``pbn_api/0079``), a Django odapplikowuje zależne migracje RAZEM
       z tą, do której się cofamy. Przywracanie samego ``pbn_api``
       zostawiało więc ``pbn_integrator`` bez tabel i sypało
       ``ProgrammingError: relacja … nie istnieje`` w ``test_mongodb_ops``.

    ``leaf_nodes()`` bez argumentu zwraca czubki CAŁEGO grafu, więc baza
    wraca dokładnie tam, gdzie była przed testem — niezależnie od tego,
    ile aplikacji zostało po drodze cofniętych.
    """
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())

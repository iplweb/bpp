Workerzy Celery emituja teraz eventy lifecycle (``worker-online``,
``worker-heartbeat``, ``worker-offline``) oraz eventy zadan
(``task-received``, ``task-started``, ``task-succeeded``,
``task-failed``) na RabbitMQ. Dzieki temu Flower poprawnie pokazuje
status workerow (online/offline) oraz historie wykonywanych zadan.
Wczesniej workerzy startowali z ``task events: OFF`` i Flower nie
widzial ich w ogole.

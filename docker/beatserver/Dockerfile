ARG BPP_BASE_TAG=latest
FROM iplweb/bpp_base:${BPP_BASE_TAG}

COPY docker/beatserver/entrypoint-beatserver.sh /app/entrypoint-beatserver.sh
# healthcheck_broker.py zostaje dla wstecznej zgodnosci: stary docker-compose w
# bpp-deploy moze go jeszcze wywolywac. Domyslny HEALTHCHECK uzywa juz lekkiej sondy.
COPY docker/beatserver/healthcheck_broker.py /app/healthcheck_broker.py
COPY docker/beatserver/healthcheck_beat.py /app/healthcheck_beat.py

ENTRYPOINT ["/app/entrypoint-beatserver.sh"]

# Lekka sonda: tylko swiezosc pliku-heartbeatu (HeartbeatScheduler dotyka go na kazdym
# ticku), bez cold-importu Django. ~30-50 ms zamiast 4-10 s -> szybki start kontenera.
HEALTHCHECK --interval=10s --timeout=5s --start-period=120s --retries=3 CMD ["python", "/app/healthcheck_beat.py"]

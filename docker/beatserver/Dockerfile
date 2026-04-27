ARG BPP_BASE_TAG=latest
FROM iplweb/bpp_base:${BPP_BASE_TAG}

COPY docker/beatserver/entrypoint-beatserver.sh /app/entrypoint-beatserver.sh
COPY docker/beatserver/healthcheck_broker.py /app/healthcheck_broker.py

ENTRYPOINT ["/app/entrypoint-beatserver.sh"]

HEALTHCHECK --interval=10s --timeout=10s --start-period=40s --retries=3 CMD ["python", "/app/healthcheck_broker.py"]

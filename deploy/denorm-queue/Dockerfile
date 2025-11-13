FROM iplweb/bpp_base:latest

COPY --chmod=755 deploy/denorm-queue/entrypoint-denorm-queue.sh /app/entrypoint-denorm-queue.sh

ENTRYPOINT ["/app/entrypoint-denorm-queue.sh"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 CMD ['CMD','true'] # disable the healthcheck

FROM iplweb/bpp_base:latest

EXPOSE 8000

COPY --chmod=755 deploy/appserver/entrypoint-appserver.sh /

RUN pip install uvicorn

#HEALTHCHECK --interval=5s --timeout=10s --retries=10 --start-period=3s \
#  CMD "bash -c 'printf \"GET / HTTP/1.1\n\n\" > /dev/tcp/127.0.0.1/8000; exit $$?;'"

ENTRYPOINT ["/bin/bash", "-c", "/entrypoint-appserver.sh"]

FROM nginx:latest

EXPOSE 80
EXPOSE 443

COPY default.conf.template /etc/nginx/conf.d/default.conf.template
COPY maintenance.html /usr/share/nginx/html/maintenance.html

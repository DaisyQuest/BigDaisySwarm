FROM nginx:1.27-alpine

COPY web_client /usr/share/nginx/html
COPY web_client/nginx.conf /etc/nginx/conf.d/default.conf
COPY web_client/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

CMD ["/entrypoint.sh"]

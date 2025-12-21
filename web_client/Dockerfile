FROM nginx:1.27-alpine

COPY web_client /usr/share/nginx/html
COPY web_client/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

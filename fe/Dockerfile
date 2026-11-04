# Non-root nginx (listens on 8080), pinned.
FROM nginxinc/nginx-unprivileged:1.27.3-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY public/ /usr/share/nginx/html/

# syntax=docker/dockerfile:1
FROM node:24-alpine AS frontend
WORKDIR /build
COPY amandaye_frontend/package.json amandaye_frontend/package-lock.json ./
RUN npm ci --ignore-scripts
COPY amandaye_frontend/ ./
RUN npm test && npm run build

FROM caddy:2-alpine
RUN apk add --no-cache libcap \
    && if [ -n "$(getcap /usr/bin/caddy)" ]; then setcap -r /usr/bin/caddy; fi \
    && apk del libcap \
    && addgroup -g 10001 app \
    && adduser -D -H -u 10001 -G app app \
    && mkdir -p /srv /data /config \
    && chown -R app:app /srv /data /config
COPY --from=frontend --chown=app:app /build/dist/ /srv/
COPY docker/gateway/Caddyfile /etc/caddy/Caddyfile
USER app
EXPOSE 8080 8443
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]

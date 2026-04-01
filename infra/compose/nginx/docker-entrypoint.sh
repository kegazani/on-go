#!/bin/sh
set -e
CONF_DIR=/etc/nginx/conf.d
mkdir -p "$CONF_DIR"
if [ ! -f "/etc/letsencrypt/live/${ON_GO_TLS_CERT_NAME}/fullchain.pem" ]; then
  cp /etc/nginx/bootstrap/http-only.conf "$CONF_DIR/default.conf"
else
  export ON_GO_TLS_API_HOST ON_GO_TLS_S3_HOST ON_GO_TLS_CERT_NAME
  envsubst '${ON_GO_TLS_API_HOST} ${ON_GO_TLS_S3_HOST} ${ON_GO_TLS_CERT_NAME}' \
    < /etc/nginx/bootstrap/on-go-ssl.conf.template > "$CONF_DIR/default.conf"
fi
exec nginx -g 'daemon off;'

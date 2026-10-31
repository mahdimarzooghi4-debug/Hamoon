#!/bin/sh
set -eu

api_proxy_upstream="${HAMOON_API_PROXY_UPSTREAM:-api:8000}"
case "$api_proxy_upstream" in
  *:*) ;;
  *)
    echo "HAMOON_API_PROXY_UPSTREAM must contain host:port" >&2
    exit 1
    ;;
esac

api_proxy_host="${api_proxy_upstream%:*}"
api_proxy_port="${api_proxy_upstream##*:}"
case "$api_proxy_host" in
  ""|*[!A-Za-z0-9._-]*)
    echo "HAMOON_API_PROXY_UPSTREAM has an invalid host" >&2
    exit 1
    ;;
esac
case "$api_proxy_port" in
  ""|*[!0-9]*)
    echo "HAMOON_API_PROXY_UPSTREAM has an invalid port" >&2
    exit 1
    ;;
esac
case "$api_proxy_host" in
  *:*)
    echo "HAMOON_API_PROXY_UPSTREAM must use a DNS host, not an IPv6 literal" >&2
    exit 1
    ;;
esac

sed "s|__HAMOON_API_PROXY_UPSTREAM__|$api_proxy_upstream|g" \
  /etc/nginx/conf.d/default.conf.template \
  > /etc/nginx/conf.d/default.conf

api_base_url="${HAMOON_WEB_API_BASE_URL:-}"
oidc_issuer_url="${HAMOON_WEB_OIDC_ISSUER_URL:-http://localhost:8081/realms/hamoon-local}"
oidc_client_id="${HAMOON_WEB_OIDC_CLIENT_ID:-hamoon-web}"
application_version="${HAMOON_APPLICATION_VERSION:-0.1.0}"
git_commit="${HAMOON_GIT_COMMIT:-development}"
image_id="${HAMOON_IMAGE_ID:-local}"
deployment_id="${HAMOON_DEPLOYMENT_ID:-local}"

api_base_url_b64="$(printf '%s' "$api_base_url" | base64 | tr -d '\n')"
oidc_issuer_url_b64="$(printf '%s' "$oidc_issuer_url" | base64 | tr -d '\n')"
oidc_client_id_b64="$(printf '%s' "$oidc_client_id" | base64 | tr -d '\n')"

cat > /usr/share/nginx/html/config.js <<EOF
window.__HAMOON_CONFIG__ = Object.freeze({
  apiBaseUrl: atob("$api_base_url_b64"),
  oidcIssuerUrl: atob("$oidc_issuer_url_b64"),
  oidcClientId: atob("$oidc_client_id_b64")
});
EOF

cat > /usr/share/nginx/html/release.json <<EOF
{
  "application_version": "$application_version",
  "git_commit": "$git_commit",
  "image_id": "$image_id",
  "deployment_id": "$deployment_id"
}
EOF

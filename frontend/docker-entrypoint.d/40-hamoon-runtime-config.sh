#!/bin/sh
set -eu

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

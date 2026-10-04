# Hamoon Web

The frontend is a standalone React + TypeScript application under `frontend/`.
Its visual tokens are copied from the canonical Hamoon Figma foundations and the UI is RTL/Persian by default.

## Local development

Run the FastAPI backend on port 8000, then:

```bash
npm install
npm run dev
```

Vite proxies `/api` and `/health` to `http://localhost:8000`.

## Container runtime

The production-shaped frontend is an immutable Nginx image:

```bash
docker build -f frontend/Dockerfile -t hamoon-web .
```

The image serves the SPA, keeps deep links such as `/auth/callback` working, and
reverse-proxies `/api`, `/health` and `/metrics` to the Hamoon API. This keeps
browser API traffic same-origin.

Environment-specific browser configuration is injected when the container starts,
not when the JavaScript bundle is built:

```text
HAMOON_WEB_API_BASE_URL
HAMOON_WEB_OIDC_ISSUER_URL
HAMOON_WEB_OIDC_CLIENT_ID
```

This preserves the deployment rule of building one immutable artifact and promoting
the same image through DEV, STAGE and PROD. `VITE_HAMOON_*` values remain development
fallbacks only.

The complete local stack exposes the web product at:

```text
http://localhost:3000
```

Authentication uses Keycloak-compatible OIDC Authorization Code + PKCE. Browser access
and refresh tokens are held in session storage, API calls attach the short-lived bearer
token, and logout delegates session termination to the IdP.

Frontend navigation is role-aware defense in depth:

- `CASEWORKER` can mount the casework routes.
- `ADMIN` can mount the Learning/Governance console.
- unauthenticated protected routes start organizational login.
- authenticated but unauthorized roles receive a local deny state without mounting the protected page.

The frontend is never the authorization authority. Every protected API still enforces
RBAC and resource scope server-side.

## Quality gates

```bash
npm run typecheck
npm run test:access
npm run build
docker build -f frontend/Dockerfile -t hamoon-web .
```

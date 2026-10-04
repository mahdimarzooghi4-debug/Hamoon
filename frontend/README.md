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

For a non-proxied deployment:

```bash
cp .env.example .env
# set VITE_HAMOON_API_BASE_URL to the internal Hamoon API origin
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
```

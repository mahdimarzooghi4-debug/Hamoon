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

Authentication is intentionally not mocked. Until the Keycloak/OIDC browser integration is wired,
authenticated calls read a real bearer token from the session key `hamoon.access_token`.
When no token exists, the product renders an authentication-required state instead of fake data.

## Quality gates

```bash
npm run typecheck
npm run build
```

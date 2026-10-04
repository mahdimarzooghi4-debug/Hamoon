const issuer = (
  import.meta.env.VITE_HAMOON_OIDC_ISSUER_URL ??
  "http://localhost:8081/realms/hamoon-local"
).replace(/\/$/, "");
const clientId = import.meta.env.VITE_HAMOON_OIDC_CLIENT_ID ?? "hamoon-web";

const ACCESS_TOKEN_KEY = "hamoon.access_token";
const REFRESH_TOKEN_KEY = "hamoon.refresh_token";
const EXPIRES_AT_KEY = "hamoon.access_token_expires_at";
const PKCE_VERIFIER_KEY = "hamoon.pkce_verifier";
const OAUTH_STATE_KEY = "hamoon.oauth_state";
const RETURN_TO_KEY = "hamoon.auth_return_to";

let refreshPromise: Promise<string | null> | null = null;

type TokenResponse = {
  access_token?: unknown;
  refresh_token?: unknown;
  expires_in?: unknown;
  refresh_expires_in?: unknown;
  token_type?: unknown;
};

export type BrowserPrincipal = {
  subject: string | null;
  displayName: string | null;
  roles: string[];
};

function base64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function randomValue(byteLength = 32): string {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  return base64Url(bytes);
}

async function challengeFor(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(verifier),
  );
  return base64Url(new Uint8Array(digest));
}

function redirectUri(): string {
  return `${window.location.origin}/auth/callback`;
}

function safeReturnTo(value: string | null): string {
  if (
    value &&
    value.startsWith("/") &&
    !value.startsWith("//") &&
    !value.startsWith("/auth/callback")
  ) {
    return value;
  }
  return "/";
}

function clearTransientAuth(): void {
  sessionStorage.removeItem(PKCE_VERIFIER_KEY);
  sessionStorage.removeItem(OAUTH_STATE_KEY);
  sessionStorage.removeItem(RETURN_TO_KEY);
}

export function clearAuthSession(): void {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(EXPIRES_AT_KEY);
}

function storeTokens(payload: TokenResponse): string {
  if (typeof payload.access_token !== "string" || payload.access_token.length === 0) {
    throw new Error("OIDC_TOKEN_RESPONSE_INVALID");
  }
  const expiresIn =
    typeof payload.expires_in === "number" && Number.isFinite(payload.expires_in)
      ? payload.expires_in
      : 300;

  sessionStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  sessionStorage.setItem(
    EXPIRES_AT_KEY,
    String(Date.now() + Math.max(30, expiresIn) * 1000),
  );
  if (
    typeof payload.refresh_token === "string" &&
    payload.refresh_token.length > 0
  ) {
    sessionStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
  }
  return payload.access_token;
}

async function tokenRequest(body: URLSearchParams): Promise<TokenResponse> {
  const response = await fetch(`${issuer}/protocol/openid-connect/token`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
  });
  const payload = (await response.json().catch(() => null)) as TokenResponse | null;
  if (!response.ok || payload === null) {
    throw new Error("OIDC_TOKEN_EXCHANGE_FAILED");
  }
  return payload;
}

export async function beginLogin(returnTo = window.location.pathname): Promise<void> {
  const verifier = randomValue(48);
  const state = randomValue(32);
  const challenge = await challengeFor(verifier);

  sessionStorage.setItem(PKCE_VERIFIER_KEY, verifier);
  sessionStorage.setItem(OAUTH_STATE_KEY, state);
  sessionStorage.setItem(RETURN_TO_KEY, safeReturnTo(returnTo));

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri(),
    response_type: "code",
    scope: "openid profile",
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
  });
  window.location.assign(
    `${issuer}/protocol/openid-connect/auth?${params.toString()}`,
  );
}

export async function completeLoginFromCallback(): Promise<string> {
  const params = new URLSearchParams(window.location.search);
  const error = params.get("error");
  if (error) {
    clearTransientAuth();
    throw new Error(`OIDC_AUTHORIZATION_FAILED:${error}`);
  }

  const code = params.get("code");
  const state = params.get("state");
  const expectedState = sessionStorage.getItem(OAUTH_STATE_KEY);
  const verifier = sessionStorage.getItem(PKCE_VERIFIER_KEY);
  const returnTo = safeReturnTo(sessionStorage.getItem(RETURN_TO_KEY));

  if (!code || !state || !expectedState || state !== expectedState || !verifier) {
    clearTransientAuth();
    throw new Error("OIDC_CALLBACK_STATE_INVALID");
  }

  try {
    const payload = await tokenRequest(
      new URLSearchParams({
        grant_type: "authorization_code",
        client_id: clientId,
        redirect_uri: redirectUri(),
        code,
        code_verifier: verifier,
      }),
    );
    storeTokens(payload);
    return returnTo;
  } finally {
    clearTransientAuth();
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = sessionStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refreshToken) {
    clearAuthSession();
    return null;
  }

  try {
    const payload = await tokenRequest(
      new URLSearchParams({
        grant_type: "refresh_token",
        client_id: clientId,
        refresh_token: refreshToken,
      }),
    );
    return storeTokens(payload);
  } catch {
    clearAuthSession();
    return null;
  }
}

export async function getAccessToken(): Promise<string | null> {
  const token = sessionStorage.getItem(ACCESS_TOKEN_KEY);
  if (!token) return null;

  const rawExpiresAt = sessionStorage.getItem(EXPIRES_AT_KEY);
  const expiresAt = rawExpiresAt ? Number(rawExpiresAt) : 0;
  if (!Number.isFinite(expiresAt) || expiresAt - Date.now() > 30_000) {
    return token;
  }

  if (refreshPromise === null) {
    refreshPromise = refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export function hasAuthSession(): boolean {
  return Boolean(sessionStorage.getItem(ACCESS_TOKEN_KEY));
}

function decodePayload(token: string): Record<string, unknown> | null {
  const segments = token.split(".");
  if (segments.length !== 3) return null;
  try {
    const raw = segments[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = raw.padEnd(Math.ceil(raw.length / 4) * 4, "=");
    const decoded = atob(padded);
    const bytes = Uint8Array.from(decoded, (char) => char.charCodeAt(0));
    const value = JSON.parse(new TextDecoder().decode(bytes)) as unknown;
    return typeof value === "object" && value !== null
      ? (value as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

export function browserPrincipal(): BrowserPrincipal | null {
  const token = sessionStorage.getItem(ACCESS_TOKEN_KEY);
  if (!token) return null;
  const claims = decodePayload(token);
  if (!claims) return null;

  const realmAccess =
    typeof claims.realm_access === "object" && claims.realm_access !== null
      ? (claims.realm_access as Record<string, unknown>)
      : null;
  const rawRoles = realmAccess?.roles;
  const roles = Array.isArray(rawRoles)
    ? rawRoles.filter((item): item is string => typeof item === "string")
    : [];
  const displayName =
    typeof claims.name === "string"
      ? claims.name
      : typeof claims.preferred_username === "string"
        ? claims.preferred_username
        : null;

  return {
    subject: typeof claims.sub === "string" ? claims.sub : null,
    displayName,
    roles,
  };
}

export function logout(): void {
  clearAuthSession();
  clearTransientAuth();
  const params = new URLSearchParams({
    client_id: clientId,
    post_logout_redirect_uri: window.location.origin,
  });
  window.location.assign(
    `${issuer}/protocol/openid-connect/logout?${params.toString()}`,
  );
}

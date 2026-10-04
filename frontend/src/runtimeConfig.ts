export type HamoonRuntimeConfig = {
  apiBaseUrl?: string;
  oidcIssuerUrl?: string;
  oidcClientId?: string;
};

declare global {
  interface Window {
    __HAMOON_CONFIG__?: HamoonRuntimeConfig;
  }
}

function nonEmpty(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

const browserConfig = window.__HAMOON_CONFIG__;

export const hamoonRuntimeConfig = Object.freeze({
  apiBaseUrl: (
    browserConfig?.apiBaseUrl ??
    import.meta.env.VITE_HAMOON_API_BASE_URL ??
    ""
  ).replace(/\/$/, ""),
  oidcIssuerUrl: (
    nonEmpty(browserConfig?.oidcIssuerUrl) ??
    nonEmpty(import.meta.env.VITE_HAMOON_OIDC_ISSUER_URL) ??
    "http://localhost:8081/realms/hamoon-local"
  ).replace(/\/$/, ""),
  oidcClientId:
    nonEmpty(browserConfig?.oidcClientId) ??
    nonEmpty(import.meta.env.VITE_HAMOON_OIDC_CLIENT_ID) ??
    "hamoon-web",
});

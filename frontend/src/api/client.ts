import { clearAuthSession, getAccessToken } from "../auth/oidc";

const apiBaseUrl = (import.meta.env.VITE_HAMOON_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string) {
    super(code);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

type RequestOptions = RequestInit & {
  auth?: boolean;
};

function errorCode(payload: unknown, status: number): string {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "detail" in payload &&
    typeof payload.detail === "object" &&
    payload.detail !== null &&
    "code" in payload.detail &&
    typeof payload.detail.code === "string"
  ) {
    return payload.detail.code;
  }
  return `HTTP_${status}`;
}

export async function requestJson<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");

  if (options.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (options.auth !== false) {
    const token = await getAccessToken();
    if (token === null || token.length === 0) {
      throw new ApiError(401, "AUTH_REQUIRED");
    }
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers,
  });

  let payload: unknown = null;
  if (response.status !== 204) {
    payload = await response.json().catch(() => null);
  }

  if (!response.ok) {
    if (response.status === 401 && options.auth !== false) {
      clearAuthSession();
      throw new ApiError(401, "AUTH_REQUIRED");
    }
    throw new ApiError(response.status, errorCode(payload, response.status));
  }

  return payload as T;
}

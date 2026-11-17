import { invalidateAuthSession } from "@/lib/auth/storage";

function isCrossSiteRenderApiUrl(url: string): boolean {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host === "onrender.com" || host.endsWith(".onrender.com");
  } catch {
    return false;
  }
}

export function resolveApiBaseUrl(
  url = process.env.NEXT_PUBLIC_API_URL,
  nodeEnv = process.env.NODE_ENV,
) {
  const configured = url?.trim();
  // Production browser calls must be same-origin (`/api/...`) when the API is
  // on Render. A leftover NEXT_PUBLIC_API_URL pointing at onrender.com keeps
  // Chrome from storing the session cookie; ignore it and use the Vercel
  // rewrite (API_PROXY_TARGET) instead.
  if (nodeEnv === "production") {
    if (
      !configured ||
      configured === "same-origin" ||
      isCrossSiteRenderApiUrl(configured)
    ) {
      return "";
    }
    return configured.replace(/\/$/, "");
  }
  if (!configured || configured === "same-origin") {
    return "http://localhost:8000";
  }
  return configured.replace(/\/$/, "");
}

const API_BASE_URL = resolveApiBaseUrl();
const CSRF_HEADER_NAME = "X-FlowPilot-Request";
const CSRF_HEADER_VALUE = "1";
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  contentType?: string;
  headers?: Record<string, string>;
  credentials?: RequestCredentials;
  /** Aborts the fetch, e.g. when a query is cancelled. */
  signal?: AbortSignal;
};

function hasCsrfHeader(headers: Record<string, string>): boolean {
  return Object.keys(headers).some((key) => key.toLowerCase() === CSRF_HEADER_NAME.toLowerCase());
}

const CREDENTIAL_CHALLENGE_PATHS = new Set([
  "/api/v1/auth/login",
  "/api/v1/auth/register",
  "/api/v1/auth/google",
]);

function _isCredentialChallengePath(path: string): boolean {
  const pathname = path.split("?", 1)[0] ?? path;
  return CREDENTIAL_CHALLENGE_PATHS.has(pathname);
}

function _shouldInvalidateSessionOn401(path: string): boolean {
  const pathname = path.split("?", 1)[0] ?? path;
  // Session restore uses /users/me. A 401 there means "logged out", not
  // "expire an in-memory session we just applied from login/register".
  if (pathname === "/api/v1/users/me") {
    return false;
  }
  return !_isCredentialChallengePath(pathname);
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  const isBlobBody =
    typeof Blob !== "undefined" && options.body instanceof Blob;
  if (options.body !== undefined && !isBlobBody) {
    headers["Content-Type"] = "application/json";
  }
  if (options.contentType) {
    headers["Content-Type"] = options.contentType;
  }
  if (options.headers) {
    Object.assign(headers, options.headers);
  }
  if (UNSAFE_METHODS.has(method) && !hasCsrfHeader(headers)) {
    headers[CSRF_HEADER_NAME] = CSRF_HEADER_VALUE;
  }

  const body: BodyInit | undefined =
    options.body === undefined
      ? undefined
      : isBlobBody
        ? (options.body as Blob)
        : JSON.stringify(options.body);
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body,
    signal: options.signal,
    credentials: options.credentials ?? "include",
  });

  // Failed login/register credentials and anonymous /users/me checks are 401s.
  // Do not treat them as a live session expiry.
  if (response.status === 401 && _shouldInvalidateSessionOn401(path)) {
    invalidateAuthSession();
  }

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    throw new ApiError(`Request failed: ${response.status}`, response.status, body);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  if (!text) {
    return undefined as T;
  }
  return JSON.parse(text) as T;
}

export function apiGet<T>(
  path: string,
  options: { signal?: AbortSignal } = {},
): Promise<T> {
  return request<T>(path, options);
}

export function apiPost<T>(
  path: string,
  body?: unknown,
  options: {
    headers?: Record<string, string>;
    credentials?: RequestCredentials;
  } = {},
): Promise<T> {
  return request<T>(path, { method: "POST", body, ...options });
}

export function apiPostFile<T>(
  path: string,
  file: Blob,
  contentType: string,
  headers?: Record<string, string>,
) {
  return request<T>(path, {
    method: "POST",
    body: file,
    contentType,
    headers,
  });
}

export function apiDelete(path: string) {
  return request<void>(path, { method: "DELETE" });
}

export function apiPatch<T>(
  path: string,
  body: unknown,
): Promise<T> {
  return request<T>(path, { method: "PATCH", body });
}

export function apiPut<T>(
  path: string,
  body: unknown,
): Promise<T> {
  return request<T>(path, { method: "PUT", body });
}

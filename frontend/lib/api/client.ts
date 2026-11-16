import { invalidateAuthSession } from "@/lib/auth/storage";

export function resolveApiBaseUrl(
  url = process.env.NEXT_PUBLIC_API_URL,
  nodeEnv = process.env.NODE_ENV,
) {
  const configured = url?.trim();
  if (configured) {
    return configured.replace(/\/$/, "");
  }
  if (nodeEnv === "production") {
    throw new Error("NEXT_PUBLIC_API_URL is required");
  }
  return "http://localhost:8000";
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

  if (response.status === 401) {
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

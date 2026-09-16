import { clearAccessToken, getAccessToken } from "@/lib/auth/storage";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  token?: string | null;
};

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const token = options.token === undefined ? getAccessToken() : options.token;
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (response.status === 401) {
    clearAccessToken();
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

export function apiGet<T>(path: string, options: { token?: string | null } = {}): Promise<T> {
  return request<T>(path, options);
}

export function apiPost<T>(
  path: string,
  body?: unknown,
  options: { token?: string | null } = {},
): Promise<T> {
  return request<T>(path, { method: "POST", body, ...options });
}

export function apiPatch<T>(
  path: string,
  body: unknown,
  options: { token?: string | null } = {},
): Promise<T> {
  return request<T>(path, { method: "PATCH", body, ...options });
}

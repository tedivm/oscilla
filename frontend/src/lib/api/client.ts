import { base } from "$app/paths";
// Note: circular import between client and authStore is intentional and safe
// because both values are accessed only inside function bodies, not at module
// initialization time. JavaScript handles this correctly.
import { authStore } from "$lib/stores/auth.js";
import { get } from "svelte/store";

/** Re-export `base` so callers can build full URLs without importing $app/paths directly. */
export { base };

/** Structured error thrown for any non-2xx HTTP response. */
export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/** Build request headers, optionally injecting the current access token. */
function buildHeaders(init?: RequestInit): HeadersInit {
  const headers: Record<string, string> = {};

  // Copy any caller-provided headers.
  if (init?.headers) {
    const provided = new Headers(init.headers as HeadersInit);
    provided.forEach((value, key) => {
      headers[key] = value;
    });
  }

  // Attach Authorization header if an access token is available.
  const { accessToken } = get(authStore);
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  // Set Content-Type for requests with a JSON body.
  if (init?.body != null && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  return headers;
}

/**
 * Core fetch wrapper used by all API modules.
 *
 * - Prepends `base` to the path so relative URLs resolve under /app/.
 * - Attaches the JWT access token when present.
 * - On 401, attempts one token refresh then retries.
 * - On second 401, logs the user out and throws ApiError.
 * - Throws ApiError for any non-2xx response.
 * - Rethrows network errors with a descriptive message.
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  // Paths starting with / are already absolute relative to origin; don't prepend base.
  const url = path.startsWith("/") ? path : `${base}${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: buildHeaders(init),
    });
  } catch (error) {
    throw new Error(`Network error fetching ${url}: ${String(error)}`);
  }

  if (response.status === 401) {
    // Avoid recursive refresh attempts for the refresh endpoint itself.
    if (path === "/api/auth/refresh") {
      await authStore.logout();
      throw new ApiError("Unauthorized — session expired", 401, null);
    }

    // Attempt a single token refresh, then retry the original request.
    try {
      await authStore.refresh();
    } catch {
      // Refresh failed — log out and abort.
      await authStore.logout();
      throw new ApiError("Unauthorized — session expired", 401, null);
    }

    // Retry with fresh token.
    let retryResponse: Response;
    try {
      retryResponse = await fetch(url, {
        ...init,
        headers: buildHeaders(init),
      });
    } catch (error) {
      throw new Error(
        `Network error on retry fetching ${url}: ${String(error)}`,
      );
    }

    if (retryResponse.status === 401) {
      await authStore.logout();
      throw new ApiError("Unauthorized — session expired", 401, null);
    }

    response = retryResponse;
  }

  if (!response.ok) {
    const rawBody = await response.text();
    let body: unknown = rawBody;
    if (rawBody.length > 0) {
      try {
        body = JSON.parse(rawBody) as unknown;
      } catch {
        // Keep plain text body when it is not valid JSON.
      }
    } else {
      body = null;
    }
    throw new ApiError(`API error ${response.status}`, response.status, body);
  }

  // 204 No Content — return undefined cast to T.
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

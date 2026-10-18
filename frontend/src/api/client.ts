/**
 * Abhijatri Base API Client
 * Configures base URL resolution, headers, and standard error handling
 * aligned with Platform Foundation 12.3 ({ code, message, details }).
 */

export const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');

export interface ApiErrorResponse {
  code?: string;
  message: string;
  details?: Record<string, unknown> | unknown[];
}

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: Record<string, unknown> | unknown[];

  constructor(status: number, message: string, code?: string, details?: Record<string, unknown> | unknown[]) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

/**
 * Universal JSON fetch helper with standard headers and typed error normalization.
 */
export async function apiRequest<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers, ...rest } = options;

  let url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined) searchParams.append(key, String(val));
    });
    const qs = searchParams.toString();
    if (qs) {
      url += (url.includes('?') ? '&' : '?') + qs;
    }
  }

  const response = await fetch(url, {
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      ...headers,
    },
    ...rest,
  });

  if (!response.ok) {
    let errorData: ApiErrorResponse = { message: `HTTP ${response.status}: ${response.statusText}` };
    try {
      errorData = await response.json();
    } catch {
      // Non-JSON error body fallback
    }
    throw new ApiError(
      response.status,
      errorData.message || response.statusText,
      errorData.code,
      errorData.details
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}


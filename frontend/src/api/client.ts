/**
 * API client configuration.
 * Base URL is read from environment variable — never hardcoded.
 * All requests go through this client so base URL and error handling
 * are centralized.
 */

// Use relative URL so requests route through the Vite dev-server proxy (/api → http://localhost:8000).
// VITE_API_BASE_URL can be set to an absolute URL in production deployments.
// Normalize base URL: strip whitespace, trailing slashes, and redundant /api or /api/v1 prefixes
// so endpoint paths starting with /api/v1/ do not accidentally duplicate prefixes.
const rawBase = (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '')
export const API_BASE = rawBase.replace(/\/api(\/v1)?\/?$/, '')

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly errorCode?: string
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`

  let response: Response
  try {
    response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...(init?.headers ?? {}),
      },
      ...init,
    })
  } catch {
    throw new ApiError(0, 'Network error — is the backend running?', 'NETWORK_ERROR')
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    let errorCode: string | undefined
    try {
      const body = await response.json()
      if (Array.isArray(body.detail)) {
        detail = body.detail
          .map((item: { msg?: string; loc?: (string | number)[] }) => {
            const field = item.loc ? item.loc[item.loc.length - 1] : undefined
            return field ? `${String(field)}: ${item.msg ?? 'Invalid value'}` : (item.msg ?? JSON.stringify(item))
          })
          .join('; ')
      } else if (typeof body.detail === 'string') {
        detail = body.detail
      } else if (body.detail) {
        detail = JSON.stringify(body.detail)
      }
      errorCode = body.error_code
    } catch {
      // ignore JSON parse failure
    }
    throw new ApiError(response.status, detail, errorCode)
  }

  return response.json() as Promise<T>
}

export const apiGet = <T>(path: string) => apiFetch<T>(path)
export const apiPost = <T>(path: string, body: unknown) =>
  apiFetch<T>(path, { method: 'POST', body: JSON.stringify(body) })
export const apiPatch = <T>(path: string, body: unknown) =>
  apiFetch<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
export const apiDelete = <T>(path: string) =>
  apiFetch<T>(path, { method: 'DELETE' })

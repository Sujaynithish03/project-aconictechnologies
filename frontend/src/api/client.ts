import axios, { AxiosError } from 'axios'

const TOKEN_KEY = 'kb_access_token'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
})

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setStoredToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

/** Attach the bearer token to every outgoing request. */
api.interceptors.request.use((config) => {
  const token = getStoredToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/**
 * Callback registered by AuthContext so a rejected token clears app state,
 * rather than this module reaching into React itself.
 */
let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // A 401 on /login or /signup is a failed attempt, not an expired session.
    const url = error.config?.url ?? ''
    const isAuthAttempt = url.includes('/login') || url.includes('/signup')
    if (error.response?.status === 401 && !isAuthAttempt) {
      setStoredToken(null)
      onUnauthorized?.()
    }
    return Promise.reject(error)
  },
)

/** Turn any axios failure into a message worth showing a user. */
export function toErrorMessage(error: unknown, fallback = 'Something went wrong.'): string {
  if (!axios.isAxiosError(error)) {
    return error instanceof Error ? error.message : fallback
  }

  if (error.code === 'ERR_NETWORK') {
    return 'Cannot reach the server. It may be starting up — try again in a moment.'
  }

  const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail

  if (typeof detail === 'string') return detail

  // FastAPI validation errors arrive as a list of {loc, msg} objects.
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        const entry = item as { loc?: unknown[]; msg?: string }
        const field = Array.isArray(entry.loc) ? entry.loc.at(-1) : undefined
        const message = (entry.msg ?? '').replace(/^Value error,\s*/, '')
        return field && field !== 'body' ? `${String(field)}: ${message}` : message
      })
      .filter(Boolean)
    if (messages.length) return messages.join(' ')
  }

  return error.response?.statusText || fallback
}

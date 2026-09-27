import { vi } from 'vitest'

type Handler = (body: unknown, init: RequestInit) => unknown
export type Routes = Record<string, Handler | unknown>

export type Call = { method: string; path: string; headers: Record<string, string>; body: unknown }

/**
 * Replaces fetch with a fake backend. Routes are keyed "METHOD /path" (query
 * string ignored); a route value is the JSON reply, or a function returning it.
 * Returning a Response lets a route set its own status.
 */
export function mockBackend(routes: Routes) {
  const calls: Call[] = []
  const fetchMock = vi.fn(async (input: string | URL, init: RequestInit = {}) => {
    const url = new URL(String(input))
    const method = (init.method || 'GET').toUpperCase()
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : undefined
    calls.push({ method, path: url.pathname, headers: (init.headers || {}) as Record<string, string>, body })
    const key = `${method} ${url.pathname}`
    if (!(key in routes)) return Response.json({ ok: false, error: `no mock for ${key}` }, { status: 404 })
    const route = routes[key]
    const reply = typeof route === 'function' ? (route as Handler)(body, init) : route
    return reply instanceof Response ? reply : Response.json(reply)
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

export const baseRoutes: Routes = {
  'GET /': new Response('ok'),
  'POST /auth/login': { ok: true, token: 'tok123', user: { id: 'u1', username: 'jordan', name: 'Jordan Reyes' } },
  'POST /auth/logout': { ok: true },
  'GET /sessions': { sessions: [] },
  'GET /session/status': { recording: false, start_time: null },
  'GET /settings': { settings: {} },
  'GET /cameras': { sources: [], assignment: { front: null, side: null }, status: {}, phone_connected: false },
  'GET /phone/link': { url: 'https://192.168.1.20:5051/?code=abc', qr_svg: '<svg></svg>', alternates: [] },
}

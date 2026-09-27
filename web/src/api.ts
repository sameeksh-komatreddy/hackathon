// Every call to the Python backend lives here, so P5 can swap this file for
// storage/repo.ts in one place.

export const BACKEND_URL = 'http://127.0.0.1:5050'
const TOKEN_KEY = 'backtrack_token'

export type User = { id: string; username: string; name: string }

export type Session = {
  id: string
  start_time: string
  end_time: string
  duration_seconds: number
  posture_score: number | null
  eye_strain_index: number | null
  avg_neck_angle: number | null
  avg_torso_angle: number | null
  avg_blink_rate: number | null
  posture_breakdown?: Record<string, number | null> | null
  eye_breakdown?: Record<string, number | null> | null
}

export type Settings = Record<string, number>

export type Insight = { risk_level?: string; summary?: string; suggestions?: string[] }

export type CameraRole = 'front' | 'side'
export type CamerasInfo = {
  sources?: { id: string; label: string }[]
  assignment?: Record<CameraRole, string | null>
  status?: Partial<Record<CameraRole, string>>
  phone_connected?: boolean
}

export type PhoneLink = { url?: string; qr_svg?: string; alternates?: string[]; error?: string }

export type StreamData = {
  pitch?: number
  roll?: number
  neck_angle?: number
  torso_angle?: number
  blink_rate?: number
  calibrated_front?: boolean
  calibrated_side?: boolean
  alerts?: string[]
  durations?: Record<string, number>
  [secsKey: string]: unknown
}

export class ApiError extends Error {
  data: unknown
  constructor(message: string, data?: unknown) {
    super(message)
    this.data = data
  }
}

const OFFLINE = "Couldn't reach the BackTrack backend at 127.0.0.1:5050."

// ---------------- token ----------------

let token: string | null = readStoredToken()

function readStoredToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}

export function hasToken(): boolean {
  return token != null
}

function setToken(value: string | null) {
  token = value
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* storage blocked: the token lasts until reload */ }
}

// <img> and EventSource can't send headers, so the camera feeds and live
// stream take the login token in the URL instead.
function authedUrl(path: string): string {
  return BACKEND_URL + path + (path.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(token || '')
}

// ---------------- request helpers ----------------

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) }
  if (token) headers.Authorization = 'Bearer ' + token
  try {
    return await fetch(BACKEND_URL + path, { ...init, headers })
  } catch {
    throw new ApiError(OFFLINE)
  }
}

/** Sends a request and returns the JSON body; throws ApiError with the backend's message on failure. */
async function call<T>(path: string, init: RequestInit = {}, fallback = 'Something went wrong.'): Promise<T> {
  const resp = await send(path, init)
  let data: Record<string, unknown> = {}
  try { data = await resp.json() } catch { /* empty or non-JSON body */ }
  if (!resp.ok || data.ok === false) {
    throw new ApiError(typeof data.error === 'string' ? data.error : fallback, data)
  }
  return data as T
}

const post = (body?: unknown): RequestInit =>
  body === undefined
    ? { method: 'POST' }
    : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }

// ---------------- auth ----------------

export async function checkBackend(): Promise<boolean> {
  try {
    return (await fetch(BACKEND_URL + '/')).ok
  } catch {
    return false
  }
}

export async function signIn(username: string, password: string): Promise<User> {
  const data = await call<{ token: string; user: User }>('/auth/login', post({ username, password }))
  setToken(data.token)
  return data.user
}

export async function signUp(username: string, password: string, name: string): Promise<User> {
  const data = await call<{ token: string; user: User }>('/auth/signup', post({ username, password, name }))
  setToken(data.token)
  return data.user
}

/** Resumes a saved login. Returns null (and forgets the token) if it's no longer valid. */
export async function resumeSession(): Promise<User | null> {
  if (!token) return null
  try {
    return (await call<{ user: User }>('/auth/me')).user
  } catch {
    setToken(null)
    return null
  }
}

export async function signOut(): Promise<void> {
  try { await send('/auth/logout', post()) } catch { /* offline: forget the token anyway */ }
  setToken(null)
}

// ---------------- sessions and history ----------------

export async function getSessions(limit: number): Promise<Session[]> {
  const data = await call<{ sessions?: Session[] }>(`/sessions?limit=${limit}`)
  return Array.isArray(data.sessions) ? data.sessions : []
}

export async function startRecording(): Promise<void> {
  await call('/session/start', post())
}

export async function stopRecording(): Promise<Session | null> {
  return (await call<{ session?: Session }>('/session/stop', post())).session ?? null
}

/** Whether this user has a session recording right now, and since when (ms). */
export async function recordingStatus(): Promise<{ recording: boolean; startMs: number | null }> {
  const data = await call<{ recording: boolean; start_time: number | null }>('/session/status')
  return { recording: !!data.recording, startMs: data.start_time != null ? data.start_time * 1000 : null }
}

export async function getInsight(metric: 'posture' | 'eye', refresh: boolean): Promise<Insight> {
  const data = await call<{ insight: Insight }>(`/insights/${metric}${refresh ? '?refresh=1' : ''}`, {},
    "Couldn't generate an AI report right now.")
  return data.insight
}

export async function deleteAllData(): Promise<Settings> {
  return (await call<{ settings?: Settings }>('/account/delete_data', post(), 'Failed to delete data.')).settings ?? {}
}

export async function exportPdf(body: {
  sections: Record<string, boolean>
  from: string
  to: string
  patient_name: string
}): Promise<Blob> {
  const resp = await send('/export/pdf', post(body))
  if (!resp.ok) {
    let msg = 'Failed to generate report.'
    try { const err = await resp.json(); if (err.error) msg = err.error } catch { /* not JSON */ }
    throw new ApiError(msg)
  }
  return resp.blob()
}

// ---------------- live tracking ----------------

export function openStream(): EventSource {
  return new EventSource(authedUrl('/stream'))
}

export function feedUrl(role: CameraRole): string {
  return authedUrl('/feed/' + role) + '&t=' + Date.now()
}

export async function recalibrate(role: CameraRole): Promise<void> {
  await send(role === 'front' ? '/recalibrate_front' : '/recalibrate_side', post())
}

export async function sendTestNotification(): Promise<void> {
  await call('/notify/test', post(), 'Failed to send.')
}

// ---------------- cameras and phone link ----------------
// Camera calls return the camera state even when the change failed, so it's
// attached to the ApiError as `data`.

export const getCameras = () => call<CamerasInfo>('/cameras')
export const assignCamera = (role: CameraRole, source: string | null) =>
  call<CamerasInfo>('/cameras', post({ [role]: source }), 'Camera change failed.')
export const swapCameras = () => call<CamerasInfo>('/cameras/swap', post(), 'Camera change failed.')
export const rescanCameras = () => call<CamerasInfo>('/cameras/rescan', post(), 'Camera change failed.')

export const getPhoneLink = (newCode: boolean) =>
  call<PhoneLink>(newCode ? '/phone/link/new' : '/phone/link', newCode ? post() : {})

// ---------------- settings ----------------

export async function getSettings(): Promise<Settings> {
  return (await call<{ settings?: Settings }>('/settings')).settings ?? {}
}

export async function saveSettings(values: Settings): Promise<Settings> {
  const resp = await send('/settings', post(values))
  let data: { settings?: Settings; errors?: Record<string, unknown> } = {}
  try { data = await resp.json() } catch { /* not JSON */ }
  if (!resp.ok) {
    throw new ApiError(Object.keys(data.errors || {}).length
      ? 'Some values were out of range and were not saved.'
      : 'Failed to save settings.')
  }
  return data.settings ?? {}
}

export async function resetSettings(): Promise<Settings> {
  return (await call<{ settings?: Settings }>('/settings/reset', post())).settings ?? {}
}

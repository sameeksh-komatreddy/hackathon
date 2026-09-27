import { createContext, useContext } from 'react'
import type { User } from '../api.ts'

export type AppState = {
  user: User
  showToast: (title: string, body: string) => void
  /** Bumped whenever sessions change (recording stopped, data deleted), so History reloads. */
  dataVersion: number
  dataChanged: () => void
}

export const AppContext = createContext<AppState | null>(null)

export function useApp(): AppState {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used inside the signed-in app')
  return ctx
}

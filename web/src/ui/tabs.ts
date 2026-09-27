export type Tab = 'history' | 'record' | 'export' | 'settings'

export const TABS: Tab[] = ['history', 'record', 'export', 'settings']

export const TAB_TITLES: Record<Tab, [string, string]> = {
  history: ['History', 'Review sessions and long-term trends.'],
  record: ['Record', 'Capture a new session from both camera angles.'],
  export: ['Export', 'Turn your history into a report you can share.'],
  settings: ['Settings', 'Tune thresholds, reminders, and appearance.'],
}

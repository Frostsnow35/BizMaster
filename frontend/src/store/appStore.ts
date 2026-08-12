import { create } from 'zustand'

interface AppState {
  sidebarCollapsed: boolean
  deepseekKey: string
  setSidebarCollapsed: (collapsed: boolean) => void
  setDeepseekKey: (key: string) => void
}

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: false,
  deepseekKey: '',
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  setDeepseekKey: (key) => set({ deepseekKey: key }),
}))

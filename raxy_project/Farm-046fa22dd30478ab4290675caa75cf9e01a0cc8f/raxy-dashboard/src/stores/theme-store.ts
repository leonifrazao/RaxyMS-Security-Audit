'use client'

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

export type ThemePreference = 'light' | 'dark'

type ThemeState = {
  theme: ThemePreference
  setTheme: (theme: ThemePreference) => void
  toggleTheme: () => ThemePreference
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: 'dark',
      setTheme: (theme) => set({ theme }),
      toggleTheme: () => {
        const nextTheme = get().theme === 'dark' ? 'light' : 'dark'
        set({ theme: nextTheme })
        return nextTheme
      },
    }),
    {
      name: 'raxy-theme-preference',
      storage: createJSONStorage(() => (typeof window !== 'undefined' ? localStorage : undefined)),
    }
  )
)

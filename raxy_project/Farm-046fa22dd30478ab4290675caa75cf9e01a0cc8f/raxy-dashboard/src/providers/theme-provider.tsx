'use client'

import { ThemeProvider as NextThemesProvider, useTheme as useNextTheme } from 'next-themes'
import { type ReactNode, useEffect } from 'react'

import { type ThemePreference, useThemeStore } from '@/stores/theme-store'

export function ThemeProvider({ children }: { children: ReactNode }) {
  const theme = useThemeStore((state) => state.theme)

  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme={theme}
      enableSystem={false}
      disableTransitionOnChange
    >
      <ThemeSynchronizer theme={theme}>{children}</ThemeSynchronizer>
    </NextThemesProvider>
  )
}

function ThemeSynchronizer({ theme, children }: { theme: ThemePreference; children: ReactNode }) {
  const { setTheme } = useNextTheme()

  useEffect(() => {
    setTheme(theme)
  }, [theme, setTheme])

  return <>{children}</>
}

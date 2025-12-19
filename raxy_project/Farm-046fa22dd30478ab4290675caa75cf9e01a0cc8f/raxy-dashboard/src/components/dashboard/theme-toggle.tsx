'use client'

import { Moon, Sun } from 'lucide-react'
import { useTheme as useNextTheme } from 'next-themes'

import { Button } from '@/components/ui/button'
import { useThemeStore } from '@/stores/theme-store'

export function ThemeToggle() {
  const toggleTheme = useThemeStore((state) => state.toggleTheme)
  const theme = useThemeStore((state) => state.theme)
  const { setTheme } = useNextTheme()

  const handleClick = () => {
    const nextTheme = toggleTheme()
    setTheme(nextTheme)
  }

  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      className="relative h-9 w-9"
      onClick={handleClick}
      aria-label={`Alternar para o tema ${theme === 'dark' ? 'claro' : 'escuro'}`}
    >
      <Sun className="h-[18px] w-[18px] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
      <Moon className="absolute h-[18px] w-[18px] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
      <span className="sr-only">Alternar tema</span>
    </Button>
  )
}

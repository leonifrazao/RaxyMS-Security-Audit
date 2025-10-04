import { type ReactNode } from 'react'

import { Header } from '@/components/dashboard/header'

export function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Header />
      <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 xl:px-12">{children}</main>
    </div>
  )
}

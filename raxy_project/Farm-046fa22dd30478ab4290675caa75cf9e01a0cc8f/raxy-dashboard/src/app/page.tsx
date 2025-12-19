import { DashboardLayout } from '@/components/dashboard/dashboard-layout'
import { AccountsTable } from '@/features/accounts/components/accounts-table'
import { KpiGrid } from '@/features/dashboard/components/kpi-grid'
import { ProxyManagerCard } from '@/features/proxy/components/proxy-manager-card'
import { DashboardHeader } from '@/features/dashboard/components/dashboard-header'
import { StatsOverview } from '@/features/dashboard/components/stats-overview'
import { PerformanceChart } from '@/features/dashboard/components/performance-chart'
import { ActivityTimeline } from '@/features/dashboard/components/activity-timeline'
import { fetchAccounts } from '@/features/accounts/data/fetch-accounts'
import { fetchDashboardKpis } from '@/features/dashboard/data/fetch-dashboard-kpis'

export default async function DashboardPage() {
  const initialSource = 'file' as const
  const [kpiData, fileAccounts, databaseAccounts] = await Promise.all([
    fetchDashboardKpis(),
    fetchAccounts('file'),
    fetchAccounts('database'),
  ])

  const allAccounts = [...fileAccounts, ...databaseAccounts]

  return (
    <>
      <DashboardHeader />
      <DashboardLayout>
        <div className="space-y-6 pb-8">
          <StatsOverview accounts={allAccounts} />
          <KpiGrid kpiData={kpiData} />
          <PerformanceChart accounts={allAccounts} />
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <ProxyManagerCard />
            </div>
            <ActivityTimeline accounts={allAccounts} />
          </div>
          <AccountsTable initialData={fileAccounts} initialSource={initialSource} />
        </div>
      </DashboardLayout>
    </>
  )
}

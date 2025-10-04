import { DashboardLayout } from '@/components/dashboard/dashboard-layout'
import { AccountsTable } from '@/features/accounts/components/accounts-table'
import { KpiGrid } from '@/features/dashboard/components/kpi-grid'
import { fetchAccounts } from '@/features/accounts/data/fetch-accounts'
import { fetchDashboardKpis } from '@/features/dashboard/data/fetch-dashboard-kpis'

export default async function DashboardPage() {
  const [kpiData, accounts] = await Promise.all([
    fetchDashboardKpis(),
    fetchAccounts(),
  ])

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <KpiGrid kpiData={kpiData} />
        <AccountsTable initialData={accounts} />
      </div>
    </DashboardLayout>
  )
}

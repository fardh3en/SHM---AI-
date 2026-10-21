import MetricCard from '../../components/ui/MetricCard'
import { useAssets } from '../../hooks/useAssets'
import { useInspections } from '../../hooks/useInspections'
import type { Inspection } from '../../api/inspections'
import styles from './MetricsStrip.module.css'

function calcAvgHealthScore(inspections: Inspection[]): string {
  const scored = inspections.filter((i) => i.health_score !== null)
  if (scored.length === 0) return '—'
  const avg = scored.reduce((sum, i) => sum + (i.health_score ?? 0), 0) / scored.length
  return avg.toFixed(1)
}

export default function MetricsStrip() {
  const { data: assetsData, isLoading: assetsLoading } = useAssets(1, 100)
  const { data: inspData, isLoading: inspLoading } = useInspections(1, 100)

  const totalAssets     = assetsData?.total ?? 0
  const totalInspections = inspData?.total ?? 0
  const completedCount  = inspData?.items.filter((i) => i.status === 'completed').length ?? 0
  const pendingCount    = inspData?.items.filter((i) => i.status === 'pending').length ?? 0
  const avgHealth       = inspData ? calcAvgHealthScore(inspData.items) : '—'

  return (
    <div className={styles.strip} aria-label="Key metrics">
      <MetricCard
        label="Registered Assets"
        value={assetsLoading ? '' : totalAssets}
        sub="structural assets monitored"
        accent="sage"
        loading={assetsLoading}
      />
      <MetricCard
        label="Total Inspections"
        value={inspLoading ? '' : totalInspections}
        sub={`${completedCount} completed`}
        accent="lilac"
        loading={inspLoading}
      />
      <MetricCard
        label="Avg Health Score"
        value={inspLoading ? '' : avgHealth}
        sub="across completed inspections"
        accent="mineral"
        loading={inspLoading}
      />
      <MetricCard
        label="Pending Inspections"
        value={inspLoading ? '' : pendingCount}
        sub="awaiting analysis"
        accent="none"
        loading={inspLoading}
      />
    </div>
  )
}

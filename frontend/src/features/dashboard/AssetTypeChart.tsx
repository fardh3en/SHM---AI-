import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { useAssets } from '../../hooks/useAssets'
import type { AssetType } from '../../api/assets'
import LoadingState from '../../components/ui/LoadingState'
import EmptyState from '../../components/ui/EmptyState'
import ErrorState from '../../components/ui/ErrorState'
import styles from './AssetTypeChart.module.css'

const TYPE_LABELS: Record<AssetType, string> = {
  bridge:   'Bridge',
  building: 'Building',
  tunnel:   'Tunnel',
  road:     'Road',
  dam:      'Dam',
  pipeline: 'Pipeline',
  other:    'Other',
}

const COLORS: string[] = [
  '#B6BDA8', // sage
  '#C0A9C5', // lilac
  '#D8C65A', // mineral
  '#85866E', // olive
  '#A77976', // rose
  '#B6BDA8', // sage repeated
  '#C0A9C5', // lilac repeated
]

export default function AssetTypeChart() {
  const { data, isLoading, isError, refetch } = useAssets(1, 100)

  if (isLoading) return <LoadingState rows={5} columns={2} />
  if (isError)   return <ErrorState message="Could not load asset data" onRetry={refetch} />

  const items = data?.items ?? []
  if (items.length === 0) {
    return (
      <EmptyState
        title="No assets registered"
        description="Register structural assets to see distribution."
      />
    )
  }

  // Count by type
  const counts: Partial<Record<AssetType, number>> = {}
  for (const asset of items) {
    counts[asset.asset_type] = (counts[asset.asset_type] ?? 0) + 1
  }

  const chartData = Object.entries(counts)
    .map(([type, count]) => ({
      type: TYPE_LABELS[type as AssetType] ?? type,
      count: count as number,
    }))
    .sort((a, b) => b.count - a.count)

  return (
    <div className={styles.container}>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 0, right: 16, bottom: 0, left: 0 }}
          barSize={14}
        >
          <XAxis
            type="number"
            tick={{ fontSize: 11, fill: 'var(--text-muted)', fontFamily: 'Inter, sans-serif' }}
            tickLine={false}
            axisLine={{ stroke: 'var(--border-medium)' }}
            allowDecimals={false}
          />
          <YAxis
            type="category"
            dataKey="type"
            tick={{ fontSize: 12, fill: 'var(--text-body)', fontFamily: 'Inter, sans-serif' }}
            tickLine={false}
            axisLine={false}
            width={64}
          />
          <Tooltip
            cursor={{ fill: 'var(--bg-subtle)', radius: 2 }}
            contentStyle={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-medium)',
              borderRadius: '4px',
              fontFamily: 'Inter, sans-serif',
              fontSize: '13px',
              color: 'var(--text-body)',
            }}
            formatter={(value: number) => [value, 'Assets']}
          />
          <Bar dataKey="count" radius={[0, 2, 2, 0]}>
            {chartData.map((_, index) => (
              <Cell key={index} fill={COLORS[index % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

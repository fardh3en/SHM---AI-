import styles from './MetricCard.module.css'

interface MetricCardProps {
  label: string
  value: string | number
  sub?: string
  accent?: 'sage' | 'lilac' | 'mineral' | 'none'
  loading?: boolean
}

export default function MetricCard({
  label,
  value,
  sub,
  accent = 'none',
  loading = false,
}: MetricCardProps) {
  return (
    <div className={[styles.card, styles[`accent-${accent}`]].join(' ')}>
      <span className={styles.label}>{label}</span>
      {loading ? (
        <span className={[styles.value, 'skeleton'].join(' ')}>&nbsp;</span>
      ) : (
        <span className={styles.value}>{value}</span>
      )}
      {sub && <span className={styles.sub}>{sub}</span>}
    </div>
  )
}

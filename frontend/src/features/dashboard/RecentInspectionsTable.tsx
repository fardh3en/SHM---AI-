import { Link } from 'react-router-dom'
import { useInspections } from '../../hooks/useInspections'
import { useAssets } from '../../hooks/useAssets'
import StatusChip from '../../components/ui/StatusChip'
import LoadingState from '../../components/ui/LoadingState'
import ErrorState from '../../components/ui/ErrorState'
import EmptyState from '../../components/ui/EmptyState'
import type { Inspection } from '../../api/inspections'
import type { Asset } from '../../api/assets'
import styles from './RecentInspectionsTable.module.css'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

function formatHealthScore(score: number | null): string {
  return score !== null ? score.toFixed(1) : '—'
}

function healthScoreClass(score: number | null): string {
  if (score === null) return styles.scoreNeutral
  if (score >= 75)    return styles.scoreGood
  if (score >= 50)    return styles.scoreWarn
  return styles.scoreCritical
}

interface AssetMap { [id: string]: Asset }

export default function RecentInspectionsTable() {
  const {
    data: inspData,
    isLoading,
    isError,
    refetch,
  } = useInspections(1, 10)

  const { data: assetsData } = useAssets(1, 100)

  const assetMap: AssetMap = {}
  assetsData?.items.forEach((a) => { assetMap[a.id] = a })

  const inspections: Inspection[] = inspData?.items ?? []

  return (
    <div className={styles.container}>
      {isLoading && <LoadingState rows={6} columns={5} />}
      {isError && (
        <ErrorState
          message="Could not load inspections. Check the backend connection."
          onRetry={refetch}
        />
      )}
      {!isLoading && !isError && inspections.length === 0 && (
        <EmptyState
          title="No inspections yet"
          description="Create an asset and run an inspection to see results here."
        />
      )}
      {!isLoading && !isError && inspections.length > 0 && (
        <div className={styles.tableWrapper} role="region" aria-label="Recent inspections">
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Asset</th>
                <th scope="col">Type</th>
                <th scope="col">Status</th>
                <th scope="col" className={styles.numCol}>Defects</th>
                <th scope="col" className={styles.numCol}>Health Score</th>
                <th scope="col">Date</th>
              </tr>
            </thead>
            <tbody>
              {inspections.map((insp) => {
                const asset = assetMap[insp.asset_id]
                return (
                  <tr key={insp.id}>
                    <td className={styles.assetCell}>
                      {asset ? (
                        <Link to={`/assets/${asset.id}`} className={styles.assetLink}>
                          <span className={styles.assetName}>{asset.name}</span>
                        </Link>
                      ) : (
                        <span className={styles.assetName}>—</span>
                      )}
                      {asset?.location && (
                        <span className={styles.assetLocation}>{asset.location}</span>
                      )}
                    </td>
                    <td>
                      <span className={styles.typeTag}>
                        {asset?.asset_type ?? '—'}
                      </span>
                    </td>
                    <td>
                      <StatusChip status={insp.status} size="sm" />
                    </td>
                    <td className={styles.numCol}>
                      {insp.defect_count > 0 ? (
                        <span className={styles.defectCount}>{insp.defect_count}</span>
                      ) : (
                        <span className={styles.noDefects}>0</span>
                      )}
                    </td>
                    <td className={styles.numCol}>
                      <span className={[styles.healthScore, healthScoreClass(insp.health_score)].join(' ')}>
                        {formatHealthScore(insp.health_score)}
                      </span>
                    </td>
                    <td className={styles.dateCell}>{formatDate(insp.created_at)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {inspData && inspData.total > 10 && (
            <div className={styles.footer}>
              <span className={styles.footerNote}>
                Showing 10 of {inspData.total} inspections
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Filter } from 'lucide-react'
import { useInspections } from '../../hooks/useInspections'
import { useAssets } from '../../hooks/useAssets'
import { isTestFixture } from '../assets/AssetListPage'
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
  const [hideTestRecords, setHideTestRecords] = useState(true)

  const {
    data: inspData,
    isLoading,
    isError,
    refetch,
  } = useInspections(1, 100)

  const { data: assetsData } = useAssets(1, 250)

  const assetMap: AssetMap = useMemo(() => {
    const map: AssetMap = {}
    assetsData?.items.forEach((a) => { map[a.id] = a })
    return map
  }, [assetsData?.items])

  const allInspections: Inspection[] = useMemo(() => inspData?.items ?? [], [inspData?.items])

  const testFixtureCount = useMemo(() => {
    return allInspections.filter((insp) => {
      const asset = assetMap[insp.asset_id]
      return (
        (asset && isTestFixture(asset)) ||
        (insp.input_path && insp.input_path.includes('test.jpg')) ||
        (insp.notes && /test fixture|automated test/i.test(insp.notes))
      )
    }).length
  }, [allInspections, assetMap])

  const displayedInspections = useMemo(() => {
    const list = hideTestRecords
      ? allInspections.filter((insp) => {
          const asset = assetMap[insp.asset_id]
          const isFixture =
            (asset && isTestFixture(asset)) ||
            (insp.input_path && insp.input_path.includes('test.jpg')) ||
            (insp.notes && /test fixture|automated test/i.test(insp.notes))
          return !isFixture
        })
      : allInspections
    return list.slice(0, 10)
  }, [allInspections, assetMap, hideTestRecords])

  return (
    <div className={styles.container}>
      {isLoading && <LoadingState rows={6} columns={5} />}
      {isError && (
        <ErrorState
          message="Could not load inspections. Check the backend connection."
          onRetry={refetch}
        />
      )}
      {!isLoading && !isError && allInspections.length === 0 && (
        <EmptyState
          title="No inspections yet"
          description="Create an asset and run an inspection to see results here."
        />
      )}
      {!isLoading && !isError && allInspections.length > 0 && (
        <div className={styles.tableWrapper} role="region" aria-label="Recent inspections">
          <div className={styles.tableToolbar}>
            <button
              type="button"
              onClick={() => setHideTestRecords((prev) => !prev)}
              className={[
                styles.fixtureToggleBtn,
                hideTestRecords ? styles.fixtureToggleBtnActive : '',
              ].join(' ')}
              title={
                hideTestRecords
                  ? 'Showing civil infrastructure inspections only. Click to display test records.'
                  : 'Showing all inspections including automated test fixtures.'
              }
            >
              <Filter size={12} />
              <span>{hideTestRecords ? 'Civil Inspections' : 'All Inspections'}</span>
            </button>
            {testFixtureCount > 0 && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {hideTestRecords
                  ? `(${testFixtureCount} test records hidden)`
                  : `(${testFixtureCount} test fixtures included)`}
              </span>
            )}
          </div>

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
              {displayedInspections.map((insp) => {
                const asset = assetMap[insp.asset_id]
                const isFixture =
                  (asset && isTestFixture(asset)) ||
                  (insp.input_path && insp.input_path.includes('test.jpg'))
                return (
                  <tr key={insp.id}>
                    <td className={styles.assetCell}>
                      {asset ? (
                        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
                          <Link to={`/assets/${asset.id}`} className={styles.assetLink}>
                            <span className={styles.assetName}>{asset.name}</span>
                          </Link>
                          {isFixture && (
                            <span className={styles.testBadge} title="Automated testing fixture">
                              Test Fixture
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className={styles.assetName}>
                          Unlinked Asset ({insp.asset_id.slice(0, 8)})
                        </span>
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
                      <Link
                        to={`/vision?inspectionId=${insp.id}`}
                        style={{ textDecoration: 'none', display: 'inline-block' }}
                        title="Open inspection in Vision Analysis"
                      >
                        <StatusChip status={insp.status} size="sm" />
                      </Link>
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
          {displayedInspections.length > 0 && (
            <div className={styles.footer}>
              <span className={styles.footerNote}>
                Showing {displayedInspections.length} {hideTestRecords ? 'civil' : 'total'} inspections
                {hideTestRecords && testFixtureCount > 0 ? ` (${testFixtureCount} test records excluded)` : ''}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

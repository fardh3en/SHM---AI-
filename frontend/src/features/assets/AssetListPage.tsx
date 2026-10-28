import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Search, Plus, MapPin, ArrowRight, Layers, Camera, Filter } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import MetricCard from '../../components/ui/MetricCard'
import StatusChip from '../../components/ui/StatusChip'
import Button from '../../components/ui/Button'
import LoadingState from '../../components/ui/LoadingState'
import ErrorState from '../../components/ui/ErrorState'
import AssetCreateModal from './AssetCreateModal'
import { useAssets } from '../../hooks/useAssets'
import type { Asset, AssetStatus } from '../../api/assets'
import styles from './AssetListPage.module.css'

export function isTestFixture(asset: { name: string; description?: string | null }): boolean {
  const n = asset.name.toLowerCase().trim()
  const d = (asset.description || '').toLowerCase()
  return (
    n.startsWith('test') ||
    n.includes('test ') ||
    n.includes(' test') ||
    n.includes('e2e') ||
    n.includes('end-to-end') ||
    n.includes('ordering test') ||
    n.includes('upload pier') ||
    n.includes('staticpool') ||
    n.includes('mock') ||
    n.includes('fixture') ||
    d.includes('test fixture') ||
    d.includes('automated test')
  )
}

export function hasArchivedEvidence(asset: Asset): boolean {
  if (asset.latest_health_score !== null) return true
  const d = (asset.description || '').toLowerCase()
  return (
    d.includes('evidence') ||
    d.includes('photograph') ||
    d.includes('crack') ||
    d.includes('inspection') ||
    d.includes('camera') ||
    d.includes('image')
  )
}

function getStatusClass(status: AssetStatus): string {
  switch (status) {
    case 'active': return styles.cardActive
    case 'under_maintenance': return styles.cardMaintenance
    case 'inactive': return styles.cardInactive
    case 'decommissioned': return styles.cardDecommissioned
    default: return ''
  }
}

function getHealthClass(score: number | null): string {
  if (score === null) return styles.healthNeutral
  if (score >= 75) return styles.healthGood
  if (score >= 50) return styles.healthWarn
  return styles.healthCritical
}

export default function AssetListPage() {
  const { data, isLoading, isError, refetch } = useAssets(1, 250)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedType, setSelectedType] = useState<string>('all')
  const [selectedStatus, setSelectedStatus] = useState<string>('all')
  const [hideTestFixtures, setHideTestFixtures] = useState<boolean>(true)

  const assets: Asset[] = useMemo(() => data?.items ?? [], [data?.items])

  const testFixtureCount = useMemo(() => assets.filter(isTestFixture).length, [assets])

  // Base assets: conditionally exclude automated test fixtures
  const baseAssets = useMemo(() => {
    return hideTestFixtures ? assets.filter((a) => !isTestFixture(a)) : assets
  }, [assets, hideTestFixtures])

  // Filtering
  const filteredAssets = useMemo(() => {
    return baseAssets.filter((asset) => {
      // Type filter
      if (selectedType !== 'all' && asset.asset_type !== selectedType) {
        return false
      }
      // Status filter
      if (selectedStatus !== 'all' && asset.status !== selectedStatus) {
        return false
      }
      // Text search
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase()
        const matchName = asset.name.toLowerCase().includes(query)
        const matchLoc = asset.location ? asset.location.toLowerCase().includes(query) : false
        const matchMat = asset.material ? asset.material.toLowerCase().includes(query) : false
        if (!matchName && !matchLoc && !matchMat) return false
      }
      return true
    })
  }, [baseAssets, selectedType, selectedStatus, searchQuery])

  // Summary Metrics (reflects base active view)
  const totalCount = baseAssets.length
  const activeCount = baseAssets.filter((a) => a.status === 'active').length
  const maintenanceCount = baseAssets.filter((a) => a.status === 'under_maintenance').length
  const scoredAssets = baseAssets.filter((a) => a.latest_health_score !== null)
  const avgHealthScore = scoredAssets.length > 0
    ? (scoredAssets.reduce((sum, a) => sum + (a.latest_health_score ?? 0), 0) / scoredAssets.length).toFixed(1)
    : '—'

  return (
    <div className={styles.container}>
      <PageHeader
        title="Asset Registry"
        description="Monitored structural inventory, physical specifications, and condition evaluations."
        breadcrumb={[
          { label: 'Dashboard', to: '/dashboard' },
          { label: 'Assets' },
        ]}
        action={
          <Button variant="primary" size="md" onClick={() => setIsModalOpen(true)}>
            <Plus size={16} />
            <span>Register Asset</span>
          </Button>
        }
      />

      <div className={styles.content}>
        {/* Summary Telemetry Strip */}
        <section aria-label="Asset registry metrics" className={styles.summaryStrip}>
          <MetricCard
            label="Monitored Assets"
            value={isLoading ? '' : totalCount}
            sub="registered structures"
            accent="sage"
            loading={isLoading}
          />
          <MetricCard
            label="Active Service"
            value={isLoading ? '' : activeCount}
            sub="normal operating condition"
            accent="mineral"
            loading={isLoading}
          />
          <MetricCard
            label="Under Maintenance"
            value={isLoading ? '' : maintenanceCount}
            sub="intervention in progress"
            accent="lilac"
            loading={isLoading}
          />
          <MetricCard
            label="Avg Health Index"
            value={isLoading ? '' : avgHealthScore}
            sub="across assessed structures"
            accent="none"
            loading={isLoading}
          />
        </section>

        {/* Filter / Search Toolbar */}
        <section aria-label="Asset filters" className={styles.toolbar}>
          <div className={styles.searchWrap}>
            <Search size={15} className={styles.searchIcon} />
            <input
              type="text"
              className={styles.searchInput}
              placeholder="Search by name, location, or material…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <select
            className={styles.filterSelect}
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            aria-label="Filter by structural category"
          >
            <option value="all">All Categories</option>
            <option value="bridge">Bridges</option>
            <option value="building">Buildings</option>
            <option value="tunnel">Tunnels</option>
            <option value="road">Roads / Flyovers</option>
            <option value="dam">Dams / Reservoirs</option>
            <option value="pipeline">Pipelines</option>
            <option value="other">Other</option>
          </select>

          <select
            className={styles.filterSelect}
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            aria-label="Filter by operational status"
          >
            <option value="all">All Operational Statuses</option>
            <option value="active">Active</option>
            <option value="under_maintenance">Under Maintenance</option>
            <option value="inactive">Inactive</option>
            <option value="decommissioned">Decommissioned</option>
          </select>

          <div className={styles.fixtureToggleWrap}>
            <button
              type="button"
              onClick={() => setHideTestFixtures((prev) => !prev)}
              className={[
                styles.fixtureToggleBtn,
                hideTestFixtures ? styles.fixtureToggleBtnActive : '',
              ].join(' ')}
              title={
                hideTestFixtures
                  ? 'Showing civil infrastructure only. Click to display test fixtures.'
                  : 'Showing all assets including automated test fixtures.'
              }
            >
              <Filter size={13} />
              <span>{hideTestFixtures ? 'Civil Structures' : 'All Structures'}</span>
            </button>
            {testFixtureCount > 0 && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {hideTestFixtures
                  ? `(${testFixtureCount} test fixtures hidden)`
                  : `(${testFixtureCount} fixtures)`}
              </span>
            )}
          </div>

          <span className={styles.resultCount}>
            {filteredAssets.length} of {totalCount} structures
          </span>
        </section>

        {/* Loading / Error States */}
        {isLoading && <LoadingState rows={6} columns={4} />}

        {isError && (
          <ErrorState
            message="Could not load structural assets from the backend. Verify FastAPI service connectivity."
            onRetry={refetch}
          />
        )}

        {/* Assets Grid */}
        {!isLoading && !isError && (
          <div className={styles.grid}>
            {filteredAssets.length === 0 ? (
              <div className={styles.emptyGrid}>
                <Layers size={36} color="var(--text-dim)" />
                <h3 className={styles.emptyTitle}>No matching structural assets</h3>
                <p className={styles.emptyDesc}>
                  {assets.length === 0
                    ? 'No structures have been registered in the database yet. Click "Register Asset" to add the first asset.'
                    : 'No assets match your search criteria. Try clearing filters or altering the search term.'}
                </p>
                {assets.length === 0 && (
                  <Button variant="primary" size="sm" onClick={() => setIsModalOpen(true)}>
                    <Plus size={14} />
                    <span>Register First Asset</span>
                  </Button>
                )}
              </div>
            ) : (
              filteredAssets.map((asset) => (
                <Link
                  key={asset.id}
                  to={`/assets/${asset.id}`}
                  className={[styles.card, getStatusClass(asset.status)].join(' ')}
                >
                  <div className={styles.cardTop}>
                    <div>
                      <div className={styles.cardTags}>
                        <span className={styles.cardCategory}>{asset.asset_type}</span>
                        {isTestFixture(asset) ? (
                          <span
                            className={styles.testBadge}
                            title="Automated testing fixture artifact"
                          >
                            Test Fixture
                          </span>
                        ) : hasArchivedEvidence(asset) ? (
                          <span
                            className={styles.evidenceTag}
                            title="Visual photographic evidence available in asset dossier"
                          >
                            <Camera size={10} /> Archived Evidence
                          </span>
                        ) : null}
                      </div>
                      <h3 className={styles.cardName}>{asset.name}</h3>
                    </div>
                    <div className={styles.healthBadge}>
                      <span className={[styles.healthScore, getHealthClass(asset.latest_health_score)].join(' ')}>
                        {asset.latest_health_score !== null ? asset.latest_health_score.toFixed(0) : '—'}
                      </span>
                      <span className={styles.healthLabel}>Health</span>
                    </div>
                  </div>

                  {asset.description && (
                    <p className={styles.cardDesc}>{asset.description}</p>
                  )}

                  <div className={styles.cardSpecs}>
                    <div className={styles.specItem}>
                      <span className={styles.specKey}>Material</span>
                      <span className={styles.specVal}>{asset.material ?? 'Not specified'}</span>
                    </div>
                    <div className={styles.specItem}>
                      <span className={styles.specKey}>Year / Life</span>
                      <span className={styles.specVal}>
                        {asset.construction_year ?? '—'}
                        {asset.design_life_years ? ` (${asset.design_life_years}y)` : ''}
                      </span>
                    </div>
                  </div>

                  <div className={styles.cardFooter}>
                    <div className={styles.cardLocation}>
                      <MapPin size={13} style={{ flexShrink: 0 }} />
                      <span>{asset.location ?? 'Location unlisted'}</span>
                    </div>
                    <div className={styles.viewAction}>
                      <StatusChip status={asset.status} size="sm" />
                      <ArrowRight size={13} className={styles.arrowIcon} />
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>
        )}
      </div>

      {/* Registration Modal Dialog */}
      <AssetCreateModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={() => refetch()}
      />
    </div>
  )
}

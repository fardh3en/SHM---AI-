import { useState, useMemo } from 'react'
import { Search, MapPin, Check, RefreshCw } from 'lucide-react'
import StatusChip from '../../components/ui/StatusChip'
import LoadingState from '../../components/ui/LoadingState'
import ErrorState from '../../components/ui/ErrorState'
import { useAssets } from '../../hooks/useAssets'
import type { Asset } from '../../api/assets'
import styles from './AssetSelector.module.css'

interface AssetSelectorProps {
  selectedAsset: Asset | null
  onSelectAsset: (asset: Asset) => void
}

export default function AssetSelector({ selectedAsset, onSelectAsset }: AssetSelectorProps) {
  const { data, isLoading, isError, refetch } = useAssets(1, 100)
  const [query, setQuery] = useState('')
  const [isChanging, setIsChanging] = useState(false)

  const assets = useMemo(() => data?.items ?? [], [data?.items])

  const filteredAssets = useMemo(() => {
    if (!query.trim()) return assets
    const q = query.toLowerCase()
    return assets.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        (a.location && a.location.toLowerCase().includes(q)) ||
        a.asset_type.toLowerCase().includes(q)
    )
  }, [assets, query])

  if (isLoading) {
    return <LoadingState rows={4} columns={3} />
  }

  if (isError) {
    return (
      <ErrorState
        message="Could not load structural assets for inspection assignment."
        onRetry={refetch}
      />
    )
  }

  // If asset is selected and not changing, show the summary telemetry card
  if (selectedAsset && !isChanging) {
    return (
      <div className={styles.selectedCard}>
        <div className={styles.selectedHeader}>
          <div className={styles.selectedTitleWrap}>
            <span className={styles.categoryTag}>{selectedAsset.asset_type}</span>
            <h3 className={styles.selectedTitle}>{selectedAsset.name}</h3>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <StatusChip status={selectedAsset.status} size="sm" />
            <button
              type="button"
              className={styles.changeBtn}
              onClick={() => setIsChanging(true)}
              aria-label="Change target asset"
            >
              <RefreshCw size={12} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
              Change
            </button>
          </div>
        </div>

        <div className={styles.selectedSpecs}>
          <div className={styles.specItem}>
            <span className={styles.specKey}>UUID</span>
            <span className={styles.specVal} style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6875rem' }}>
              {selectedAsset.id.slice(0, 8)}…{selectedAsset.id.slice(-4)}
            </span>
          </div>

          <div className={styles.specItem}>
            <span className={styles.specKey}>Location</span>
            <span className={styles.specVal}>{selectedAsset.location ?? 'Unspecified'}</span>
          </div>

          <div className={styles.specItem}>
            <span className={styles.specKey}>Material</span>
            <span className={styles.specVal}>{selectedAsset.material ?? 'Not specified'}</span>
          </div>

          <div className={styles.specItem}>
            <span className={styles.specKey}>Health Index</span>
            <span className={styles.specVal}>
              {selectedAsset.latest_health_score !== null
                ? `${selectedAsset.latest_health_score.toFixed(1)} / 100`
                : 'Not evaluated'}
            </span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div className={styles.pickerBox}>
        <div className={styles.searchRow}>
          <Search size={15} className={styles.searchIcon} />
          <input
            type="text"
            className={styles.searchInput}
            placeholder="Search structural assets by name, type, or location…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus={isChanging}
          />
        </div>

        <ul className={styles.assetList} role="listbox" aria-label="Monitored structural assets">
          {filteredAssets.length === 0 ? (
            <li style={{ padding: '16px', textAlign: 'center', color: 'var(--text-dim)', fontSize: '13px' }}>
              No structural assets match your search.
            </li>
          ) : (
            filteredAssets.map((asset) => {
              const isCurrent = selectedAsset?.id === asset.id
              return (
                <li key={asset.id}>
                  <button
                    type="button"
                    className={[styles.assetItem, isCurrent ? styles.assetItemActive : ''].join(' ')}
                    onClick={() => {
                      onSelectAsset(asset)
                      setIsChanging(false)
                    }}
                    role="option"
                    aria-selected={isCurrent}
                  >
                    <div className={styles.assetMain}>
                      <span className={styles.categoryTag}>{asset.asset_type}</span>
                      <span className={styles.assetName}>{asset.name}</span>
                      {asset.location && (
                        <span className={styles.assetLoc}>
                          <MapPin size={11} />
                          <span>{asset.location}</span>
                        </span>
                      )}
                    </div>

                    <div className={styles.assetRight}>
                      {asset.latest_health_score !== null && (
                        <span className={styles.scoreBadge} title="Latest composite health score">
                          {asset.latest_health_score.toFixed(0)}
                        </span>
                      )}
                      <StatusChip status={asset.status} size="sm" />
                      {isCurrent && <Check size={16} color="var(--color-mineral)" />}
                    </div>
                  </button>
                </li>
              )
            })
          )}
        </ul>
      </div>
    </div>
  )
}

import { useState, useMemo, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useAssets } from '../../hooks/useAssets'
import { useAssetInspections } from '../../hooks/useAssetInspections'
import PageHeader from '../../components/layout/PageHeader'
import LoadingState from '../../components/ui/LoadingState'
import ErrorState from '../../components/ui/ErrorState'
import EmptyState from '../../components/ui/EmptyState'
import Viewport3D from './Viewport3D'
import ComponentDetailPanel from './ComponentDetailPanel'
import StatusLegend from './StatusLegend'
import type { StructuralComponentData } from './models/types'
import { Box, ExternalLink, Activity, Layers } from 'lucide-react'
import styles from './StructuralHealthPage.module.css'

export default function StructuralHealthPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: assetsData, isLoading: assetsLoading, isError: assetsError, refetch } = useAssets()

  const assets = useMemo(() => assetsData?.items ?? [], [assetsData])

  // Get active asset ID from URL query param or fallback to first asset
  const urlAssetId = searchParams.get('assetId')
  const [selectedAssetId, setSelectedAssetId] = useState<string>('')

  useEffect(() => {
    if (assets.length > 0) {
      if (urlAssetId && assets.some((a) => a.id === urlAssetId)) {
        setSelectedAssetId(urlAssetId)
      } else if (!selectedAssetId) {
        setSelectedAssetId(assets[0].id)
      }
    }
  }, [assets, urlAssetId, selectedAssetId])

  const selectedAsset = useMemo(
    () => assets.find((a) => a.id === selectedAssetId) ?? assets[0] ?? null,
    [assets, selectedAssetId]
  )

  // Fetch inspections for the selected asset
  const { data: inspections = [] } = useAssetInspections(selectedAsset?.id)

  // Selected structural component in the 3D scene
  const [selectedComponent, setSelectedComponent] = useState<StructuralComponentData | null>(null)

  // When asset changes, reset component selection and update URL
  const handleAssetChange = (newAssetId: string) => {
    setSelectedAssetId(newAssetId)
    setSelectedComponent(null)
    setSearchParams({ assetId: newAssetId }, { replace: true })
  }

  if (assetsLoading) {
    return (
      <div className={styles.container}>
        <PageHeader
          title="3D Structural Health Visualization"
          description="Interactive parametric digital twin and structural member condition telemetry."
        />
        <div className={styles.content}>
          <LoadingState rows={4} columns={3} />
        </div>
      </div>
    )
  }

  if (assetsError) {
    return (
      <div className={styles.container}>
        <PageHeader
          title="3D Structural Health Visualization"
          description="Interactive parametric digital twin and structural member condition telemetry."
        />
        <div className={styles.content}>
          <ErrorState
            message="Could not retrieve the structural asset registry from the backend API."
            onRetry={() => {
              void refetch()
            }}
          />
        </div>
      </div>
    )
  }

  if (!selectedAsset) {
    return (
      <div className={styles.container}>
        <PageHeader
          title="3D Structural Health Visualization"
          description="Interactive parametric digital twin and structural member condition telemetry."
        />
        <div className={styles.content}>
          <EmptyState
            title="No Registered Assets"
            description="Register a structural asset in the Asset Registry to view its 3D structural model."
            action={{
              label: 'Go to Asset Registry',
              onClick: () => (window.location.href = '/assets'),
            }}
          />
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <PageHeader
        title="3D Structural Health Visualization"
        description="Interactive spatial twin and condition telemetry. Select individual members to inspect localized findings."
      />

      <div className={styles.content}>
        {/* Asset Selector & Meta Bar */}
        <div className={styles.controlBar} role="region" aria-label="Asset Selection">
          <div className={styles.selectorGroup}>
            <label htmlFor="asset-select" className={styles.selectorLabel}>
              Active Asset:
            </label>
            <select
              id="asset-select"
              className={styles.assetSelect}
              value={selectedAsset.id}
              onChange={(e) => handleAssetChange(e.target.value)}
              aria-label="Select asset for 3D structural visualization"
            >
              {assets.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.asset_type.toUpperCase()})
                </option>
              ))}
            </select>
          </div>

          <div className={styles.metaStats}>
            <div className={styles.statItem}>
              <Layers size={14} />
              <span>Typology:</span>
              <strong>{selectedAsset.asset_type.toUpperCase()}</strong>
            </div>

            <div className={styles.statItem}>
              <Activity size={14} />
              <span>Health Score:</span>
              <strong>
                {selectedAsset.latest_health_score !== null
                  ? `${selectedAsset.latest_health_score}/100`
                  : 'N/A'}
              </strong>
            </div>

            <div className={styles.statItem}>
              <Box size={14} />
              <span>Inspections:</span>
              <strong>{inspections.length}</strong>
            </div>

            <Link
              to={`/assets/${selectedAsset.id}`}
              className={styles.linkDetail}
              title="Open full asset dossier"
            >
              <span>Asset Dossier</span>
              <ExternalLink size={12} />
            </Link>
          </div>
        </div>

        {/* Viewport and Component Details Layout */}
        <div className={styles.mainLayout}>
          <div className={styles.viewportColumn}>
            <Viewport3D
              asset={selectedAsset}
              inspections={inspections}
              selectedComponentId={selectedComponent?.id ?? null}
              onSelectComponent={(comp) => setSelectedComponent(comp)}
            />
            <StatusLegend />
          </div>

          <div className={styles.panelColumn}>
            <ComponentDetailPanel
              asset={selectedAsset}
              inspections={inspections}
              component={selectedComponent}
              onDeselect={() => setSelectedComponent(null)}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

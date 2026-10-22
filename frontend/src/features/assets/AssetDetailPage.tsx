import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  MapPin,
  Activity,
  FileText,
  Layers,
  Box,
  ScanLine,
  Camera,
} from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import StatusChip from '../../components/ui/StatusChip'
import LoadingState from '../../components/ui/LoadingState'
import ErrorState from '../../components/ui/ErrorState'
import { useAsset } from '../../hooks/useAssets'
import { useAssetInspections } from '../../hooks/useAssetInspections'
import AssetEvidenceGallery from './AssetEvidenceGallery'
import InspectionComparisonCard from './InspectionComparisonCard'
import styles from './AssetDetailPage.module.css'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

function getConditionTier(score: number | null): { label: string; className: string } {
  if (score === null) return { label: 'Not Assessed', className: styles.healthNeutral }
  if (score >= 75) return { label: 'Good / Stable', className: styles.healthGood }
  if (score >= 50) return { label: 'Moderate Risk', className: styles.healthWarn }
  return { label: 'Critical / Action Needed', className: styles.healthCritical }
}

export default function AssetDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: asset, isLoading: assetLoading, isError: assetError, refetch: refetchAsset } = useAsset(id)
  const { data: inspections, isLoading: inspLoading, isError: inspError, refetch: refetchInsp } = useAssetInspections(id)

  if (assetLoading) {
    return (
      <div className={styles.content}>
        <LoadingState rows={8} columns={4} />
      </div>
    )
  }

  if (assetError || !asset) {
    return (
      <div className={styles.content}>
        <ErrorState
          message={`Could not load structural dossier for asset ID "${id}".`}
          onRetry={refetchAsset}
        />
      </div>
    )
  }

  const currentYear = new Date().getFullYear()
  const assetAge = asset.construction_year != null ? currentYear - asset.construction_year : null
  const ageLabel = assetAge !== null
    ? assetAge >= 0
      ? `${assetAge} years in service`
      : 'Planned / Future construction'
    : 'Age unrecorded'
  const condition = getConditionTier(asset.latest_health_score)

  return (
    <div className={styles.container}>
      <PageHeader
        title={asset.name}
        description={`Structural category: ${asset.asset_type.toUpperCase()} · Monitored civil engineering asset dossier.`}
        breadcrumb={[
          { label: 'Dashboard', to: '/dashboard' },
          { label: 'Assets', to: '/assets' },
          { label: asset.name },
        ]}
        action={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <StatusChip status={asset.status} size="md" />
          </div>
        }
      />

      <div className={styles.content}>
        {/* Back Link & 3D Model Quick Action */}
        <div className={styles.backBar} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Link to="/assets" className={styles.backLink}>
            <ArrowLeft size={15} />
            <span>Return to Asset Registry</span>
          </Link>
          <Link to={`/structural-health?assetId=${asset.id}`} className={styles.backLink}>
            <Box size={15} />
            <span>Interactive 3D Structural Health</span>
          </Link>
        </div>

        {/* Overview Dossier Split */}
        <div className={styles.dossierGrid}>
          {/* Specifications Panel */}
          <section className={styles.panel} aria-labelledby="specs-title">
            <h2 id="specs-title" className={styles.panelTitle}>
              <Layers size={16} />
              <span>Physical Specifications &amp; Attributes</span>
            </h2>
            <hr className={styles.panelRule} />

            <div className={styles.specsList}>
              <div className={styles.specRow}>
                <span className={styles.specLabel}>Asset UUID</span>
                <span className={styles.specValue} style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                  {asset.id}
                </span>
              </div>

              <div className={styles.specRow}>
                <span className={styles.specLabel}>Category</span>
                <span className={styles.specValue} style={{ textTransform: 'capitalize' }}>
                  {asset.asset_type}
                </span>
              </div>

              <div className={styles.specRow}>
                <span className={styles.specLabel}>Primary Material</span>
                <span className={styles.specValue}>
                  {asset.material ?? 'Not recorded'}
                </span>
              </div>

              <div className={styles.specRow}>
                <span className={styles.specLabel}>Location / Coordinates</span>
                <span className={styles.specValue} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <MapPin size={13} color="var(--color-mineral)" />
                  <span>{asset.location ?? 'Unspecified'}</span>
                </span>
              </div>

              <div className={styles.specRow}>
                <span className={styles.specLabel}>Construction Year &amp; Age</span>
                <span className={styles.specValue}>
                  {asset.construction_year
                    ? `${asset.construction_year} (${ageLabel})`
                    : 'Unknown'}
                </span>
              </div>

              <div className={styles.specRow}>
                <span className={styles.specLabel}>Design Service Life</span>
                <span className={styles.specValue}>
                  {asset.design_life_years
                    ? `${asset.design_life_years} years`
                    : 'Not specified'}
                </span>
              </div>
            </div>

            {asset.description && (
              <div className={styles.descSection}>
                <span className={styles.specLabel}>Engineering Description</span>
                <p className={styles.descText}>{asset.description}</p>
              </div>
            )}
          </section>

          {/* Health Index Panel */}
          <section className={styles.panel} aria-labelledby="health-title">
            <h2 id="health-title" className={styles.panelTitle}>
              <Activity size={16} />
              <span>Structural Health Status</span>
            </h2>
            <hr className={styles.panelRule} />

            <div className={styles.healthCenter}>
              <span className={[styles.healthValue, condition.className].join(' ')}>
                {asset.latest_health_score !== null ? asset.latest_health_score.toFixed(1) : '—'}
              </span>
              <span className={[styles.healthTier, condition.className].join(' ')}>
                {condition.label}
              </span>
            </div>

            <div className={styles.healthMeta}>
              <div className={styles.healthMetaItem}>
                <span className={styles.healthMetaKey}>Operational State</span>
                <StatusChip status={asset.status} size="sm" />
              </div>
              <div className={styles.healthMetaItem}>
                <span className={styles.healthMetaKey}>Total Inspections</span>
                <span className={styles.healthMetaVal}>
                  {inspections ? inspections.length : '…'}
                </span>
              </div>
              <div className={styles.healthMetaItem}>
                <span className={styles.healthMetaKey}>Dossier Registered</span>
                <span className={styles.healthMetaVal}>{formatDate(asset.created_at)}</span>
              </div>
            </div>
          </section>
        </div>

        {/* Visual Evidence Photographic Archive */}
        <AssetEvidenceGallery assetId={asset.id} assetName={asset.name} />

        {/* Associated Inspection Ledger */}
        <section className={styles.inspectionsSection} aria-labelledby="ledger-title">
          <div className={styles.sectionHeader}>
            <h2 id="ledger-title" className={styles.sectionTitle}>
              Associated Inspection History
            </h2>
            <span className={styles.sectionCount}>
              {inspections ? `${inspections.length} recorded events` : 'Loading…'}
            </span>
          </div>

          {inspLoading && <LoadingState rows={4} columns={6} />}

          {inspError && (
            <ErrorState
              message="Failed to retrieve inspection ledger for this structural asset."
              onRetry={refetchInsp}
            />
          )}

          {!inspLoading && !inspError && (
            <>
              {inspections && inspections.length === 0 ? (
                <div className={styles.emptyLedger}>
                  <FileText size={32} color="var(--text-dim)" style={{ margin: '0 auto 12px' }} />
                  <p>No inspection records have been recorded for this structural asset yet.</p>
                </div>
              ) : (
                <div className={styles.tableWrapper}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th scope="col" className={styles.thumbCell}>Evidence</th>
                        <th scope="col">Date</th>
                        <th scope="col">Source</th>
                        <th scope="col">Status</th>
                        <th scope="col" className={styles.numCol}>Defect Count</th>
                        <th scope="col" className={styles.numCol}>Health Score</th>
                        <th scope="col">Methodology</th>
                        <th scope="col">Inspector / Pipeline Notes</th>
                        <th scope="col">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {inspections?.map((insp) => (
                        <tr key={insp.id}>
                          <td className={styles.thumbCell}>
                            {insp.input_path ? (
                              <img
                                src={insp.input_path}
                                alt="Evidence thumbnail"
                                className={styles.evidenceThumb}
                                loading="lazy"
                              />
                            ) : (
                              <div className={styles.thumbPlaceholder} title="No photographic media">
                                <Camera size={14} />
                              </div>
                            )}
                          </td>
                          <td style={{ whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>
                            {formatDate(insp.created_at)}
                          </td>
                          <td>
                            <span className={styles.sourceTag}>{insp.source}</span>
                          </td>
                          <td>
                            <StatusChip status={insp.status} size="sm" />
                          </td>
                          <td className={styles.numCol}>
                            {insp.defect_count > 0 ? (
                              <span className={styles.defectNum}>{insp.defect_count}</span>
                            ) : (
                              <span className={styles.noDefects}>0</span>
                            )}
                          </td>
                          <td className={styles.numCol}>
                            <span className={styles.scoreCell}>
                              {insp.health_score !== null ? insp.health_score.toFixed(1) : 'Not Assessed'}
                            </span>
                          </td>
                          <td>
                            <span className={styles.methodTag}>
                              {insp.health_score !== null ? 'SHM-AI v1.0 (Noisy-OR)' : 'Not Assessed'}
                            </span>
                          </td>
                          <td className={styles.notesCell}>
                            {insp.notes ?? '—'}
                            {insp.error_message && (
                              <div className={styles.errorBanner}>
                                Error: {insp.error_message}
                              </div>
                            )}
                          </td>
                          <td>
                            <div className={styles.actionLinks}>
                              <Link
                                to={`/vision?inspectionId=${insp.id}`}
                                className={styles.actionIconBtn}
                                title="Open in Vision Analysis"
                              >
                                <ScanLine size={12} />
                                <span>Vision</span>
                              </Link>
                              <Link
                                to={`/reports?assetId=${asset.id}&inspectionId=${insp.id}`}
                                className={styles.actionIconBtn}
                                title="Compile Engineering Report"
                              >
                                <FileText size={12} />
                                <span>Report</span>
                              </Link>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </section>

        {/* Comparative Structural Change Tracking */}
        <InspectionComparisonCard assetId={asset.id} inspections={inspections ?? []} />
      </div>
    </div>
  )
}

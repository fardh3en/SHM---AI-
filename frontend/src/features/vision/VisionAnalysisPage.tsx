import { useState, useMemo, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useInspections } from '../../hooks/useInspections'
import { useAssets } from '../../hooks/useAssets'
import { useInspectionDetections } from '../../hooks/useDetections'
import { inspectionsApi } from '../../api/inspections'
import { resolveMediaUrl } from '../../api/client'
import PageHeader from '../../components/layout/PageHeader'
import LoadingState from '../../components/ui/LoadingState'
import ErrorState from '../../components/ui/ErrorState'
import EmptyState from '../../components/ui/EmptyState'
import StatusChip from '../../components/ui/StatusChip'
import {
  ScanLine,
  Play,
  RotateCw,
  Layers,
  AlertTriangle,
  Info,
  ShieldCheck,
  UploadCloud,
} from 'lucide-react'
import styles from './VisionAnalysisPage.module.css'

export default function VisionAnalysisPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()

  const { data: inspData, isLoading: inspLoading, isError: inspError, refetch } = useInspections(1, 100)
  const { data: assetsData } = useAssets(1, 100)

  const inspections = useMemo(() => inspData?.items ?? [], [inspData])
  const assets = useMemo(() => assetsData?.items ?? [], [assetsData])

  // Select inspection from URL param or default to the first one
  const urlInspId = searchParams.get('inspectionId')
  const [selectedInspId, setSelectedInspId] = useState<string>('')

  useEffect(() => {
    if (inspections.length > 0) {
      if (urlInspId && inspections.some((i) => i.id === urlInspId)) {
        setSelectedInspId(urlInspId)
      } else if (!selectedInspId) {
        setSelectedInspId(inspections[0].id)
      }
    }
  }, [inspections, urlInspId, selectedInspId])

  const selectedInspection = useMemo(
    () => inspections.find((i) => i.id === selectedInspId) ?? inspections[0] ?? null,
    [inspections, selectedInspId]
  )

  const associatedAsset = useMemo(() => {
    if (!selectedInspection) return null
    return assets.find((a) => a.id === selectedInspection.asset_id) ?? null
  }, [selectedInspection, assets])

  // Fetch real detections for this inspection
  const {
    data: detections = [],
    isLoading: detectionsLoading,
  } = useInspectionDetections(selectedInspection?.id)

  // Interactive selection and overlay toggles
  const [selectedDetectionId, setSelectedDetectionId] = useState<string | null>(null)
  const [showBoxes, setShowBoxes] = useState(true)
  const [showLabels, setShowLabels] = useState(true)

  // Mutation to run vision pipeline
  const runMutation = useMutation({
    mutationFn: (id: string) => inspectionsApi.run(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['inspections'] })
      void queryClient.invalidateQueries({ queryKey: ['inspection-detections', selectedInspId] })
    },
  })

  const handleInspectionChange = (newId: string) => {
    setSelectedInspId(newId)
    setSelectedDetectionId(null)
    setSearchParams({ inspectionId: newId }, { replace: true })
  }

  if (inspLoading) {
    return (
      <div className={styles.container}>
        <PageHeader
          title="Vision Analysis & Defect Measurement"
          description="Automated crack detection, bounding box localization, and calibrated geometry."
        />
        <div className={styles.content}>
          <LoadingState rows={4} columns={3} />
        </div>
      </div>
    )
  }

  if (inspError) {
    return (
      <div className={styles.container}>
        <PageHeader
          title="Vision Analysis & Defect Measurement"
          description="Automated crack detection, bounding box localization, and calibrated geometry."
        />
        <div className={styles.content}>
          <ErrorState
            message="Failed to retrieve inspection records from API."
            onRetry={() => {
              void refetch()
            }}
          />
        </div>
      </div>
    )
  }

  if (!selectedInspection) {
    return (
      <div className={styles.container}>
        <PageHeader
          title="Vision Analysis & Defect Measurement"
          description="Automated crack detection, bounding box localization, and calibrated geometry."
        />
        <div className={styles.content}>
          <EmptyState
            title="No Inspections Found"
            description="Submit an inspection image through Inspection Studio to begin computer vision defect mapping."
            action={{
              label: 'Go to Inspection Studio',
              onClick: () => (window.location.href = '/inspections'),
            }}
          />
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <PageHeader
        title="Vision Analysis & Defect Measurement"
        description="Deep learning defect detection, bounding box localization, and geometric measurement."
        breadcrumb={[
          { label: 'Dashboard', to: '/dashboard' },
          { label: 'Vision Analysis' },
        ]}
      />

      <div className={styles.content}>
        {/* Inspection Selector & Action Toolbar */}
        <div className={styles.controlBar} role="region" aria-label="Inspection Selection">
          <div className={styles.selectorGroup}>
            <label htmlFor="inspection-select" className={styles.selectorLabel}>
              Active Inspection:
            </label>
            <select
              id="inspection-select"
              className={styles.selectInput}
              value={selectedInspection.id}
              onChange={(e) => handleInspectionChange(e.target.value)}
              aria-label="Select inspection to review vision analysis"
            >
              {inspections.map((i) => {
                const assetName = assets.find((a) => a.id === i.asset_id)?.name || i.asset_id.slice(0, 8)
                const dateStr = new Date(i.created_at).toLocaleDateString('en-GB', {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric',
                })
                return (
                  <option key={i.id} value={i.id}>
                    {assetName} • {dateStr} ({i.defect_count} defects, {i.status.toUpperCase()})
                  </option>
                )
              })}
            </select>
          </div>

          <div className={styles.headerMetaActions}>
            <StatusChip status={selectedInspection.status} size="md" />

            <Link
              to="/inspections"
              className={styles.runButton}
              style={{
                background: 'var(--color-mineral)',
                color: '#111413',
                border: 'none',
                fontWeight: 600,
              }}
              title="Upload new crack photograph to inspect"
            >
              <UploadCloud size={14} />
              <span>Upload Crack Image</span>
            </Link>

            {selectedInspection.status !== 'completed' && selectedInspection.input_path && (
              <button
                type="button"
                className={styles.runButton}
                disabled={runMutation.isPending}
                onClick={() => runMutation.mutate(selectedInspection.id)}
                title="Execute YOLO inference on this inspection image"
              >
                {runMutation.isPending ? <RotateCw className="spin" size={14} /> : <Play size={14} />}
                <span>{runMutation.isPending ? 'Processing Vision Model...' : 'Execute Vision Analysis'}</span>
              </button>
            )}

            {associatedAsset && (
              <Link
                to={`/assets/${associatedAsset.id}`}
                className={styles.runButton}
                style={{ background: 'transparent', borderColor: 'var(--border-medium)' }}
                title="Open asset profile"
              >
                <Layers size={14} />
                <span>Asset Profile</span>
              </Link>
            )}
          </div>
        </div>

        {/* Inspection Metadata Summary */}
        <div className={styles.summaryCard} role="region" aria-label="Inspection Details">
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Monitored Structure</span>
            <span className={styles.summaryValue}>{associatedAsset?.name || 'Unlinked Asset'}</span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Typology / Category</span>
            <span className={styles.summaryValue}>
              {associatedAsset?.asset_type.toUpperCase() || 'CIVIL ASSET'}
            </span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Source Media</span>
            <span className={styles.summaryValue}>
              {selectedInspection.source.toUpperCase()}
            </span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Identified Defects</span>
            <span className={styles.summaryValue} style={{ color: selectedInspection.defect_count > 0 ? '#E0564A' : '#B6BDA8' }}>
              {selectedInspection.defect_count} Detected
            </span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Processing Latency</span>
            <span className={styles.summaryValue}>
              {selectedInspection.processing_time_ms !== null
                ? `${selectedInspection.processing_time_ms.toFixed(1)} ms`
                : '—'}
            </span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Health Assessment Score</span>
            <span className={styles.summaryValue}>
              {selectedInspection.health_score !== null
                ? `${selectedInspection.health_score.toFixed(1)} / 100`
                : selectedInspection.status === 'completed'
                  ? 'Unverified'
                  : 'Pending'}
            </span>
          </div>
        </div>

        {/* Dual Viewports: Raw Evidence vs AI Detection Overlay */}
        <div className={styles.dualViewportGrid}>
          {/* Left: Original Inspection Evidence */}
          <div className={styles.viewportPanel}>
            <div className={styles.viewportHeader}>
              <div className={styles.viewportTitle}>
                <Layers size={14} color="#B6BDA8" />
                <span>Original Evidence Photographic Source</span>
              </div>
              <span>{selectedInspection.source.toUpperCase()}</span>
            </div>

            <div className={styles.imageCanvasWrapper}>
              {selectedInspection.input_path ? (
                <img
                  src={resolveMediaUrl(selectedInspection.input_path)}
                  alt="Raw structural inspection evidence"
                  className={styles.displayImage}
                />
              ) : (
                <div style={{ color: 'rgba(243, 239, 231, 0.6)', padding: '2rem', textAlign: 'center' }}>
                  <Info size={32} style={{ margin: '0 auto 8px auto', display: 'block' }} />
                  <span>Manual visual survey — No image evidence uploaded.</span>
                </div>
              )}
            </div>
          </div>

          {/* Right: Computer Vision Detection Overlay */}
          <div className={styles.viewportPanel}>
            <div className={styles.viewportHeader}>
              <div className={styles.viewportTitle}>
                <ScanLine size={14} color="#D8C65A" />
                <span>Defect Localization &amp; Bounding Boxes</span>
              </div>

              <div className={styles.toggleGroup}>
                <button
                  type="button"
                  className={`${styles.toggleBtn} ${showBoxes ? styles.toggleBtnActive : ''}`}
                  onClick={() => setShowBoxes((prev) => !prev)}
                >
                  Boxes
                </button>
                <button
                  type="button"
                  className={`${styles.toggleBtn} ${showLabels ? styles.toggleBtnActive : ''}`}
                  onClick={() => setShowLabels((prev) => !prev)}
                >
                  Labels
                </button>
              </div>
            </div>

            <div className={styles.imageCanvasWrapper}>
              {selectedInspection.input_path ? (
                <>
                  <img
                    src={resolveMediaUrl(selectedInspection.input_path)}
                    alt="Analyzed structural evidence with defect overlays"
                    className={styles.displayImage}
                  />

                  {/* Normalized Bounding Box Overlays */}
                  {showBoxes && (
                    <div className={styles.detectionOverlayLayer}>
                      {detections.map((det, index) => {
                        const isSelected = selectedDetectionId === det.id
                        const leftPct = det.bbox_x1 * 100
                        const topPct = det.bbox_y1 * 100
                        const widthPct = (det.bbox_x2 - det.bbox_x1) * 100
                        const heightPct = (det.bbox_y2 - det.bbox_y1) * 100

                        return (
                          <div
                            key={det.id}
                            className={`${styles.boundingBox} ${isSelected ? styles.boundingBoxActive : ''}`}
                            style={{
                              left: `${leftPct}%`,
                              top: `${topPct}%`,
                              width: `${widthPct}%`,
                              height: `${heightPct}%`,
                            }}
                            onClick={() => setSelectedDetectionId(det.id)}
                            title={`Defect #${index + 1}: ${det.defect_type.toUpperCase()} (${(det.confidence * 100).toFixed(0)}%)`}
                          >
                            {showLabels && (
                              <div className={styles.boxLabelTag}>
                                {det.defect_type.toUpperCase()} {(det.confidence * 100).toFixed(0)}%
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </>
              ) : (
                <div style={{ color: 'rgba(243, 239, 231, 0.6)', padding: '2rem', textAlign: 'center' }}>
                  <Info size={32} style={{ margin: '0 auto 8px auto', display: 'block' }} />
                  <span>No visual media available for computer vision processing.</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Defect Inventory Table */}
        <div className={styles.tableSection}>
          <div className={styles.tableHeaderRow}>
            <h3 className={styles.tableTitle}>
              <AlertTriangle size={16} color="#E0564A" />
              <span>Detected Defect Inventory ({detections.length})</span>
            </h3>
            {selectedDetectionId && (
              <button
                type="button"
                className={styles.toggleBtn}
                onClick={() => setSelectedDetectionId(null)}
              >
                Clear Selection
              </button>
            )}
          </div>

          {detectionsLoading ? (
            <LoadingState rows={3} columns={5} />
          ) : detections.length > 0 ? (
            <div className={styles.tableWrap}>
              <table className={styles.defectTable}>
                <thead>
                  <tr>
                    <th>Ref #</th>
                    <th>Classification</th>
                    <th>Confidence</th>
                    <th>Area (px²)</th>
                    <th>Length (px)</th>
                    <th>Width (px)</th>
                    <th>Orientation</th>
                    <th>Normalized BBox Coordinates</th>
                  </tr>
                </thead>
                <tbody>
                  {detections.map((det, idx) => {
                    const isSelected = selectedDetectionId === det.id
                    return (
                      <tr
                        key={det.id}
                        className={`${styles.defectTableRow} ${isSelected ? styles.defectTableRowActive : ''}`}
                        onClick={() => setSelectedDetectionId(det.id)}
                      >
                        <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                          #{idx + 1}
                        </td>
                        <td>
                          <span
                            style={{
                              fontFamily: 'var(--font-mono)',
                              textTransform: 'uppercase',
                              fontWeight: 600,
                              color: det.defect_type === 'crack' ? '#E0564A' : '#D8C65A',
                            }}
                          >
                            {det.defect_type}
                          </span>
                        </td>
                        <td>
                          <div className={styles.confidenceMeter}>
                            <div className={styles.meterBar}>
                              <div
                                className={styles.meterFill}
                                style={{ width: `${det.confidence * 100}%` }}
                              />
                            </div>
                            <span>{(det.confidence * 100).toFixed(1)}%</span>
                          </div>
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {det.area_px !== null ? `${det.area_px.toLocaleString()} px²` : '—'}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {det.length_px !== null ? `${det.length_px.toFixed(1)} px` : '—'}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {det.width_px !== null ? `${det.width_px.toFixed(2)} px` : '—'}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {det.orientation_deg !== null ? `${det.orientation_deg.toFixed(1)}°` : '—'}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)' }}>
                          [{det.bbox_x1.toFixed(2)}, {det.bbox_y1.toFixed(2)}] → [{det.bbox_x2.toFixed(2)}, {det.bbox_y2.toFixed(2)}]
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)' }}>
              {selectedInspection.status === 'completed'
                ? 'Zero defect detections recorded for this inspection.'
                : 'Inspection has not yet been processed by the vision pipeline.'}
            </div>
          )}
        </div>

        {/* Engineering Provenance Notice */}
        <div className={styles.provenanceNotice} role="note">
          <strong>Computer Vision Architecture Notice:</strong> Defect classifications, bounding box
          coordinates, and pixel geometries are generated deterministically by the configured vision
          pipeline. Defect measurements (area, length, average width) are reported in
          pixel space; physical millimeter calibration requires known Ground Sampling Distance (GSD) or
          on-site reference fiducials.
        </div>

        {/* Model Verification & Benchmark Evaluation Protocol */}
        <div className={styles.protocolCard} role="region" aria-label="Model Verification & Evaluation Protocol">
          <div className={styles.protocolHeader}>
            <div className={styles.protocolTitle}>
              <ShieldCheck size={16} color="var(--color-mineral)" />
              <span>Model Verification &amp; Evaluation Protocol</span>
            </div>
            <span className={styles.protocolBadge}>Validation Protocol Active</span>
          </div>

          <div className={styles.protocolGrid}>
            <div className={styles.protocolItem}>
              <span className={styles.protocolLabel}>Formal Benchmark Status</span>
              <span className={styles.protocolVal}>
                Awaiting local ground-truth benchmark annotation ingestion. No synthetic or fabricated precision/recall/mAP scores are reported without verified test sets.
              </span>
            </div>

            <div className={styles.protocolItem}>
              <span className={styles.protocolLabel}>Target Evaluation Metrics</span>
              <span className={styles.protocolVal}>
                <span className={styles.protocolValCode}>mAP@50</span> (PASCAL VOC / COCO metric) and <span className={styles.protocolValCode}>mAP@50:95</span> with strict IoU threshold <span className={styles.protocolValCode}>&ge; 0.50</span> for defect localization.
              </span>
            </div>

            <div className={styles.protocolItem}>
              <span className={styles.protocolLabel}>Validated Defect Classes</span>
              <span className={styles.protocolVal}>
                Crack, Spall, Corrosion / Rebar Exposure, Efflorescence, Delamination.
              </span>
            </div>

            <div className={styles.protocolItem}>
              <span className={styles.protocolLabel}>Physical Metric Calibration</span>
              <span className={styles.protocolVal}>
                Geometric measurements in pixels require GSD calibration: <span className={styles.protocolValCode}>GSD = (sensor_pitch &times; distance) / focal_length</span> before physical engineering sign-off.
              </span>
            </div>
          </div>

          <div className={styles.protocolDisclaimer}>
            <strong>Engineering Compliance Disclosure:</strong> Under structural engineering evaluation protocols, detection confidence reflects convolutional neural network activation probabilities and does not equate to structural failure risk. Structural risk assessment is governed by the ACI 318 / Eurocode 2 limit-state criteria implemented in the deterministic Structural Assessment engine.
          </div>
        </div>
      </div>
    </div>
  )
}

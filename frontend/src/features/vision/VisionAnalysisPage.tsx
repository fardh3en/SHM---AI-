import { useState, useMemo, useEffect } from 'react'
import { useSearchParams, Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useInspections } from '../../hooks/useInspections'
import { useAssets } from '../../hooks/useAssets'
import { useInspectionDetections } from '../../hooks/useDetections'
import { useGenerateReport } from '../../hooks/useReports'
import { inspectionsApi } from '../../api/inspections'
import { systemApi } from '../../api/system'
import { resolveMediaUrl } from '../../api/client'
import type { Detection } from '../../api/detections'
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
  Sliders,
  Ruler,
  CheckCircle2,
  HelpCircle,
  FileText,
  ExternalLink,
} from 'lucide-react'
import styles from './VisionAnalysisPage.module.css'

interface ImageDimensions {
  width: number
  height: number
}

/**
 * Extracts point coordinates from a GeoJSON-style Polygon, MultiPolygon,
 * or raw coordinate array and formats them into an SVG points string.
 */
function getPolygonPoints(maskPolygon: unknown, imgW: number, imgH: number): string[] {
  if (!maskPolygon || typeof maskPolygon !== 'object') return []
  const poly = maskPolygon as Record<string, unknown>
  let rings: number[][][] = []

  if (poly.type === 'Polygon' && Array.isArray(poly.coordinates)) {
    rings = poly.coordinates as number[][][]
  } else if (poly.type === 'MultiPolygon' && Array.isArray(poly.coordinates)) {
    const multi = poly.coordinates as number[][][][]
    rings = multi.map((m) => m[0]).filter((r): r is number[][] => Array.isArray(r))
  } else if (Array.isArray(poly.coordinates)) {
    rings = [poly.coordinates as number[][]]
  }

  const pointStrings: string[] = []
  for (const ring of rings) {
    if (!Array.isArray(ring) || ring.length < 3) continue
    // Check if points are normalized [0, 1] or absolute image pixels
    const isNormalized = ring.every((p) => Array.isArray(p) && p[0] <= 1.05 && p[1] <= 1.05)
    const pts = ring
      .filter((p) => Array.isArray(p) && p.length >= 2)
      .map((p) => {
        const x = isNormalized ? p[0] * imgW : p[0]
        const y = isNormalized ? p[1] * imgH : p[1]
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
    if (pts.length >= 3) {
      pointStrings.push(pts.join(' '))
    }
  }
  return pointStrings
}

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
  const [showMasks, setShowMasks] = useState(true)
  const [showBoxes, setShowBoxes] = useState(true)
  const [showLabels, setShowLabels] = useState(true)
  const [imageError, setImageError] = useState(false)
  const [imageDimensions, setImageDimensions] = useState<ImageDimensions | null>(null)

  // Interactive scale calibration state
  const [showScalePanel, setShowScalePanel] = useState(false)
  const [manualScale, setManualScale] = useState<number | null>(null)
  const [scaleInputVal, setScaleInputVal] = useState('')

  // System information query for active model
  const { data: systemInfo } = useQuery({
    queryKey: ['system-info'],
    queryFn: () => systemApi.info(),
    staleTime: 60_000,
  })

  useEffect(() => {
    setImageError(false)
    setImageDimensions(null)
  }, [selectedInspId])

  // Determine effective calibration status across detections or manual scale override
  const isBackendCalibrated = useMemo(() => {
    return detections.some(
      (d) => d.calibration_status === 'calibrated' || (d.length_mm !== null && d.length_mm !== undefined)
    )
  }, [detections])

  const effectiveScale = useMemo(() => {
    if (manualScale !== null && manualScale > 0) return manualScale
    if (isBackendCalibrated) {
      const calibDet = detections.find(
        (d) => d.length_mm !== null && d.length_mm !== undefined && d.length_px && d.length_px > 0
      )
      if (calibDet && calibDet.length_mm && calibDet.length_px) {
        return calibDet.length_mm / calibDet.length_px
      }
    }
    return null
  }, [manualScale, isBackendCalibrated, detections])

  const isCalibrated = effectiveScale !== null && effectiveScale > 0

  // Mutation to run vision pipeline
  const runMutation = useMutation({
    mutationFn: (id: string) => inspectionsApi.run(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['inspections'] })
      void queryClient.invalidateQueries({ queryKey: ['inspection-detections', selectedInspId] })
    },
  })

  // Report generation mutation & state
  const navigate = useNavigate()
  const generateReportMutation = useGenerateReport()
  const [reportSuccessNotice, setReportSuccessNotice] = useState<{
    filename: string
    downloadUrl: string
    healthScore: number | null
    recommendedAction: string
  } | null>(null)
  const [reportErrorNotice, setReportErrorNotice] = useState<string | null>(null)

  const isCompleted = selectedInspection?.status === 'completed'

  const handleGenerateReport = () => {
    if (!selectedInspection || !isCompleted) return
    setReportErrorNotice(null)
    setReportSuccessNotice(null)

    generateReportMutation.mutate(
      {
        asset_id: selectedInspection.asset_id,
        inspection_id: selectedInspection.id,
        format: 'html',
      },
      {
        onSuccess: (data) => {
          setReportSuccessNotice({
            filename: data.filename,
            downloadUrl: `/api/v1/reports/${data.filename}`,
            healthScore: data.health_score,
            recommendedAction: data.recommended_action,
          })
          // Open or navigate to the report preview and make the saved report accessible in the existing archive
          navigate(
            `/reports?assetId=${selectedInspection.asset_id}&inspectionId=${selectedInspection.id}&reportFile=${data.filename}`
          )
        },
        onError: (err) => {
          setReportErrorNotice(
            err instanceof Error ? err.message : 'Report compilation failed. Please try again.'
          )
        },
      }
    )
  }

  const handleInspectionChange = (newId: string) => {
    setSelectedInspId(newId)
    setSelectedDetectionId(null)
    setSearchParams({ inspectionId: newId }, { replace: true })
  }

  const handleApplyCustomScale = () => {
    const val = parseFloat(scaleInputVal)
    if (!isNaN(val) && val > 0) {
      setManualScale(val)
    }
  }

  const handleClearCustomScale = () => {
    setManualScale(null)
    setScaleInputVal('')
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

  const imgW = imageDimensions?.width || 1280
  const imgH = imageDimensions?.height || 720

  return (
    <div className={styles.container}>
      <PageHeader
        title="Vision Analysis & Defect Measurement"
        description="Deep learning defect detection, segmentation polygon tracing, and calibration-aware geometry."
        breadcrumb={[
          { label: 'Dashboard', to: '/dashboard' },
          { label: 'Vision Analysis' },
        ]}
      />

      <div className={styles.content}>
        {/* Inspection Selector & Action Toolbar */}
        <div className={styles.controlBar} role="region" aria-label="Inspection Selection and Actions">
          <div className={styles.selectorRow}>
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

            <div className={styles.badgeGroup}>
              <StatusChip status={selectedInspection.status} size="md" />

              {/* Calibration Status Indicator Badge */}
              {isCalibrated ? (
                <span className={styles.calibratedBadge} title="Physical dimensions calibrated">
                  <CheckCircle2 size={12} />
                  CALIBRATED ({effectiveScale.toFixed(3)} mm/px)
                </span>
              ) : (
                <span className={styles.requiresCalibrationBadge} title="Image uncalibrated: measurements in pixel units only">
                  <AlertTriangle size={12} />
                  UNCALIBRATED (PIXEL UNITS ONLY)
                </span>
              )}
            </div>
          </div>

          <div className={styles.actionsRow}>
            {/* 1. Prominent Generate Engineering Report Button */}
            <button
              type="button"
              className={styles.generateReportBtn}
              disabled={!isCompleted || generateReportMutation.isPending}
              onClick={handleGenerateReport}
              title={
                isCompleted
                  ? "Compile formal engineering report dossier for this inspection"
                  : `Cannot compile report: Inspection status is '${selectedInspection.status}'. A completed inspection is required.`
              }
            >
              {generateReportMutation.isPending ? (
                <RotateCw className="spin" size={14} />
              ) : (
                <FileText size={14} />
              )}
              <span>
                {generateReportMutation.isPending
                  ? 'Compiling Dossier...'
                  : 'Generate Engineering Report'}
              </span>
            </button>

            {/* 2. Analyze Another Image Action */}
            <Link
              to="/inspections"
              className={styles.runButton}
              style={{
                background: 'var(--color-mineral)',
                color: '#111413',
                border: 'none',
                fontWeight: 600,
              }}
              title="Start a new inspection with a different crack photograph"
            >
              <UploadCloud size={14} />
              <span>Analyze Another Image</span>
            </Link>

            {/* 3. Metric Scale Calibration Tool Toggle */}
            <button
              type="button"
              className={styles.runButton}
              style={{
                background: showScalePanel ? 'var(--color-mineral)' : 'var(--bg-surface)',
                color: showScalePanel ? '#111413' : 'var(--text-primary)',
                borderColor: 'var(--border-medium)',
              }}
              onClick={() => setShowScalePanel((prev) => !prev)}
              title="Configure Ground Sampling Distance or reference millimeter scale"
            >
              <Ruler size={14} />
              <span>{showScalePanel ? 'Hide Calibration' : 'Set Scale / Calibrate'}</span>
            </button>

            {/* 4. Standalone Vision Pipeline Execution if not completed */}
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

            {/* 5. Associated Asset Profile Link */}
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

          {/* Feedback Banners for Report Generation */}
          {reportErrorNotice && (
            <div className={styles.reportNoticeError}>
              <span>{reportErrorNotice}</span>
              <button
                type="button"
                onClick={() => setReportErrorNotice(null)}
                style={{ background: 'none', border: 'none', color: '#FAF9F5', cursor: 'pointer', fontWeight: 'bold' }}
              >
                ✕
              </button>
            </div>
          )}

          {reportSuccessNotice && (
            <div className={styles.reportNoticeSuccess}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <CheckCircle2 size={15} color="#66765A" />
                <span>
                  Engineering Report <strong>{reportSuccessNotice.filename}</strong> compiled successfully!
                </span>
                <span>• Health: {reportSuccessNotice.healthScore ?? '—'}/100</span>
                <span>• Action: {reportSuccessNotice.recommendedAction.toUpperCase()}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Link
                  to={`/reports?assetId=${selectedInspection.asset_id}&inspectionId=${selectedInspection.id}&reportFile=${reportSuccessNotice.filename}`}
                  className={styles.inlineActionLink}
                >
                  <FileText size={12} /> View in Reports
                </Link>
                <a
                  href={reportSuccessNotice.downloadUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.inlineActionLink}
                >
                  <ExternalLink size={12} /> Open Tab
                </a>
              </div>
            </div>
          )}
        </div>

        {/* Interactive Scale Setting Panel */}
        {showScalePanel && (
          <div className={styles.scaleControlPanel} role="region" aria-label="Measurement Calibration Controls">
            <div className={styles.scalePanelHeader}>
              <div className={styles.scalePanelTitle}>
                <Sliders size={14} color="var(--color-mineral)" />
                <span>Metric Scale Calibration Tool (Ground Sampling Distance)</span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                {manualScale ? `Active Manual Scale: ${manualScale.toFixed(4)} mm/px` : 'Default: Uncalibrated'}
              </span>
            </div>

            <div className={styles.scaleControlsRow}>
              <div className={styles.scaleInputWrap}>
                <label htmlFor="custom-scale-input" className={styles.selectorLabel}>
                  Scale (mm/px):
                </label>
                <input
                  id="custom-scale-input"
                  type="number"
                  step="0.01"
                  min="0.001"
                  placeholder="e.g. 0.25"
                  value={scaleInputVal}
                  onChange={(e) => setScaleInputVal(e.target.value)}
                  className={styles.scaleInput}
                />
                <button
                  type="button"
                  className={styles.presetBtn}
                  onClick={handleApplyCustomScale}
                  disabled={!scaleInputVal || parseFloat(scaleInputVal) <= 0}
                >
                  Apply Scale
                </button>
                {manualScale !== null && (
                  <button type="button" className={styles.presetBtn} onClick={handleClearCustomScale}>
                    Reset Scale
                  </button>
                )}
              </div>

              <div className={styles.presetGroup}>
                <span className={styles.presetLabel}>Presets:</span>
                <button
                  type="button"
                  className={`${styles.presetBtn} ${manualScale === 0.1 ? styles.presetBtnActive : ''}`}
                  onClick={() => {
                    setManualScale(0.1)
                    setScaleInputVal('0.10')
                  }}
                  title="Close-up macro crack gauge (~100-150mm standoff)"
                >
                  0.10 mm/px (Close Macro)
                </button>
                <button
                  type="button"
                  className={`${styles.presetBtn} ${manualScale === 0.35 ? styles.presetBtnActive : ''}`}
                  onClick={() => {
                    setManualScale(0.35)
                    setScaleInputVal('0.35')
                  }}
                  title="Handheld structural photograph (~0.5m standoff)"
                >
                  0.35 mm/px (Handheld 0.5m)
                </button>
                <button
                  type="button"
                  className={`${styles.presetBtn} ${manualScale === 1.2 ? styles.presetBtnActive : ''}`}
                  onClick={() => {
                    setManualScale(1.2)
                    setScaleInputVal('1.20')
                  }}
                  title="Standoff inspection survey (~2m distance)"
                >
                  1.20 mm/px (Standoff 2m)
                </button>
              </div>
            </div>

            <p style={{ margin: 0, fontSize: '11px', color: 'var(--text-muted)' }}>
              <strong>Notice:</strong> Physical millimeter dimensions require known scale or Ground Sampling Distance (GSD). Applying a scale dynamically populates calibrated millimeter measurements in the defect table below.
            </p>
          </div>
        )}

        {/* Diagnostic Quality & Calibration Warning Alert */}
        {!isCalibrated && (
          <div className={styles.diagnosticBanner} role="alert">
            <Info size={18} className={styles.diagnosticIcon} />
            <div>
              <strong>Photogrammetric Screening Notice:</strong> This inspection photograph is currently{' '}
              <strong>uncalibrated</strong>. Crack length, width, and vertical extent are reported accurately in{' '}
              <strong>pixel units</strong>. Millimeter dimensions are withheld from formal engineering conclusions until calibrated via known reference target or Ground Sampling Distance.
              Click <strong>Set Scale / Calibrate</strong> above to preview calibrated metric values.
            </div>
          </div>
        )}

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
            <span className={styles.summaryLabel}>Metric Calibration</span>
            <span className={styles.summaryValue} style={{ color: isCalibrated ? '#4ECDC4' : '#D8C65A', fontSize: '0.8125rem' }}>
              {isCalibrated ? `Calibrated (${effectiveScale?.toFixed(3)} mm/px)` : 'Uncalibrated (Pixel Space)'}
            </span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Subsurface Crack Depth</span>
            <span className={styles.summaryValue} style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              Not Measured (2D Optical)
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
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Active Detector</span>
            <span className={styles.summaryValue} style={{ fontSize: '0.8125rem', fontFamily: 'monospace' }}>
              {systemInfo?.default_model || 'shm_ai_crack_seg_finetune_15e_best.pt'}
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

            <div
              className={styles.imageCanvasWrapper}
              style={imageDimensions ? { aspectRatio: `${imageDimensions.width} / ${imageDimensions.height}` } : undefined}
            >
              {selectedInspection.input_path ? (
                imageError ? (
                  <div style={{ color: 'var(--color-clay, #d97736)', padding: '2.5rem 1.5rem', textAlign: 'center' }}>
                    <AlertTriangle size={32} style={{ margin: '0 auto 8px auto', display: 'block' }} />
                    <div style={{ fontWeight: 600, marginBottom: '6px' }}>Evidence Image Missing on Server</div>
                    <div style={{ fontSize: '0.8125rem', opacity: 0.85, wordBreak: 'break-all' }}>
                      File path <code>{selectedInspection.input_path}</code> was not found on the server disk.
                    </div>
                  </div>
                ) : (
                  <img
                    src={resolveMediaUrl(selectedInspection.input_path)}
                    alt="Raw structural inspection evidence"
                    className={styles.displayImage}
                    onError={() => setImageError(true)}
                  />
                )
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
                <span>Defect Localization, Polygons &amp; Bounding Boxes</span>
              </div>

              <div className={styles.toggleGroup}>
                <button
                  type="button"
                  className={`${styles.toggleBtn} ${showMasks ? styles.toggleBtnActive : ''}`}
                  onClick={() => setShowMasks((prev) => !prev)}
                  title="Toggle segmentation polygon overlays"
                >
                  Masks
                </button>
                <button
                  type="button"
                  className={`${styles.toggleBtn} ${showBoxes ? styles.toggleBtnActive : ''}`}
                  onClick={() => setShowBoxes((prev) => !prev)}
                  title="Toggle bounding boxes"
                >
                  Boxes
                </button>
                <button
                  type="button"
                  className={`${styles.toggleBtn} ${showLabels ? styles.toggleBtnActive : ''}`}
                  onClick={() => setShowLabels((prev) => !prev)}
                  title="Toggle defect classification labels"
                >
                  Labels
                </button>
              </div>
            </div>

            <div
              className={styles.imageCanvasWrapper}
              style={imageDimensions ? { aspectRatio: `${imageDimensions.width} / ${imageDimensions.height}` } : undefined}
            >
              {selectedInspection.input_path ? (
                imageError ? (
                  <div style={{ color: 'var(--color-clay, #d97736)', padding: '2.5rem 1.5rem', textAlign: 'center' }}>
                    <AlertTriangle size={32} style={{ margin: '0 auto 8px auto', display: 'block' }} />
                    <div style={{ fontWeight: 600, marginBottom: '6px' }}>Defect Overlay Unavailable</div>
                    <div style={{ fontSize: '0.8125rem', opacity: 0.85 }}>
                      Underlying evidence image was not found on disk.
                    </div>
                  </div>
                ) : (
                  <>
                    <img
                      src={resolveMediaUrl(selectedInspection.input_path)}
                      alt="Analyzed structural evidence with defect overlays"
                      className={styles.displayImage}
                      onError={() => setImageError(true)}
                      onLoad={(e) => {
                        const target = e.currentTarget
                        if (target.naturalWidth > 0 && target.naturalHeight > 0) {
                          setImageDimensions({
                            width: target.naturalWidth,
                            height: target.naturalHeight,
                          })
                        }
                      }}
                    />

                    {/* SVG Segmentation Mask Overlay */}
                    {showMasks && (
                      <svg
                        viewBox={`0 0 ${imgW} ${imgH}`}
                        className={styles.maskSvgLayer}
                        preserveAspectRatio="none"
                      >
                        {detections.map((det) => {
                          const isSelected = selectedDetectionId === det.id
                          const rings = getPolygonPoints(det.mask_polygon, imgW, imgH)
                          return rings.map((ptsStr, ringIdx) => (
                            <polygon
                              key={`${det.id}-poly-${ringIdx}`}
                              points={ptsStr}
                              className={`${styles.maskPolygon} ${isSelected ? styles.maskPolygonActive : ''}`}
                              onClick={() => setSelectedDetectionId(det.id)}
                            >
                              <title>{`${det.defect_type.toUpperCase()} (#${det.id.slice(0, 4)}): ${(det.confidence * 100).toFixed(0)}%`}</title>
                            </polygon>
                          ))
                        })}
                      </svg>
                    )}

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
                )
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
              <span>Detected Defect Inventory &amp; Geometric Measurements ({detections.length})</span>
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
            <LoadingState rows={3} columns={6} />
          ) : detections.length > 0 ? (
            <div className={styles.tableWrap}>
              <table className={styles.defectTable}>
                <thead>
                  <tr>
                    <th>Ref #</th>
                    <th>Classification</th>
                    <th>Confidence</th>
                    <th>Pixel Length (px)</th>
                    <th>Calibrated Length (mm)</th>
                    <th>Pixel Width (px)</th>
                    <th>Calibrated Width (mm)</th>
                    <th>Vertical Extent (px)</th>
                    <th>Calibrated Vert (mm)</th>
                    <th>Area (px²)</th>
                    <th>Calibrated Area (mm²)</th>
                    <th>Subsurface Depth</th>
                  </tr>
                </thead>
                <tbody>
                  {detections.map((det: Detection, idx) => {
                    const isSelected = selectedDetectionId === det.id

                    // Compute vertical extent in pixels if not directly stored
                    const vertPx =
                      det.vertical_extent_px ??
                      (det.bbox_y2 > det.bbox_y1 ? Math.round((det.bbox_y2 - det.bbox_y1) * imgH * 10) / 10 : null)

                    // Calibrated physical dimensions
                    const effLengthMm =
                      det.length_mm ??
                      (effectiveScale && det.length_px ? det.length_px * effectiveScale : null)
                    const effWidthMm =
                      det.width_mm ??
                      (effectiveScale && det.width_px ? det.width_px * effectiveScale : null)
                    const effVertMm =
                      effectiveScale && vertPx ? vertPx * effectiveScale : null
                    const effAreaMm2 =
                      det.area_mm2 ??
                      (effectiveScale && det.area_px ? det.area_px * effectiveScale * effectiveScale : null)

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

                        {/* Pixel Length */}
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {det.length_px !== null && det.length_px !== undefined ? `${det.length_px.toFixed(1)} px` : '—'}
                        </td>

                        {/* Calibrated Length */}
                        <td>
                          {effLengthMm !== null ? (
                            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#4ECDC4' }}>
                              {effLengthMm.toFixed(1)} mm
                            </span>
                          ) : (
                            <button
                              type="button"
                              className={styles.requiresCalibrationBadge}
                              onClick={(e) => {
                                e.stopPropagation()
                                setShowScalePanel(true)
                              }}
                              title="Click to set calibration scale"
                            >
                              Requires Calibration
                            </button>
                          )}
                        </td>

                        {/* Pixel Width */}
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {det.width_px !== null && det.width_px !== undefined ? `${det.width_px.toFixed(2)} px` : '—'}
                        </td>

                        {/* Calibrated Width */}
                        <td>
                          {effWidthMm !== null ? (
                            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#4ECDC4' }}>
                              {effWidthMm.toFixed(2)} mm
                            </span>
                          ) : (
                            <button
                              type="button"
                              className={styles.requiresCalibrationBadge}
                              onClick={(e) => {
                                e.stopPropagation()
                                setShowScalePanel(true)
                              }}
                              title="Click to set calibration scale"
                            >
                              Requires Calibration
                            </button>
                          )}
                        </td>

                        {/* Vertical Extent (px) */}
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {vertPx !== null ? `${vertPx.toFixed(1)} px` : '—'}
                        </td>

                        {/* Calibrated Vertical Extent */}
                        <td>
                          {effVertMm !== null ? (
                            <span style={{ fontFamily: 'var(--font-mono)', color: '#4ECDC4' }}>
                              {effVertMm.toFixed(1)} mm
                            </span>
                          ) : (
                            <button
                              type="button"
                              className={styles.requiresCalibrationBadge}
                              onClick={(e) => {
                                e.stopPropagation()
                                setShowScalePanel(true)
                              }}
                              title="Click to set calibration scale"
                            >
                              Requires Calibration
                            </button>
                          )}
                        </td>

                        {/* Pixel Area */}
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {det.area_px !== null && det.area_px !== undefined ? `${det.area_px.toLocaleString()} px²` : '—'}
                        </td>

                        {/* Calibrated Area */}
                        <td>
                          {effAreaMm2 !== null ? (
                            <span style={{ fontFamily: 'var(--font-mono)', color: '#4ECDC4' }}>
                              {effAreaMm2.toFixed(1)} mm²
                            </span>
                          ) : (
                            <button
                              type="button"
                              className={styles.requiresCalibrationBadge}
                              onClick={(e) => {
                                e.stopPropagation()
                                setShowScalePanel(true)
                              }}
                              title="Click to set calibration scale"
                            >
                              Requires Calibration
                            </button>
                          )}
                        </td>

                        {/* Subsurface Depth Status */}
                        <td>
                          <span
                            className={styles.depthStatusBadge}
                            title="2D optical photography cannot measure subsurface crack depth. NDT required."
                          >
                            <HelpCircle size={10} />
                            Not Measured (2D)
                          </span>
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
          pipeline. Defect measurements (area, length, average width, vertical extent) are reported in
          pixel space; physical millimeter calibration requires known Ground Sampling Distance (GSD) or
          on-site reference fiducials. Physical millimeter dimensions are never fabricated. Subsurface depth cannot be derived from optical surface imagery.
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
                Fine-tuned YOLO11 instance segmentation (15 epochs). Mask precision: 73.7%, Recall: 58.1%, mAP50: 58.0% on independent test benchmark. Zero false positives on concrete negative tests at &ge; 0.50 confidence.
              </span>
            </div>

            <div className={styles.protocolItem}>
              <span className={styles.protocolLabel}>Target Evaluation Metrics</span>
              <span className={styles.protocolVal}>
                <span className={styles.protocolValCode}>mAP@50</span> (PASCAL VOC / COCO metric) and <span className={styles.protocolValCode}>mAP@50:95</span> with strict IoU threshold <span className={styles.protocolValCode}>&ge; 0.50</span> for defect localization.
              </span>
            </div>

            <div className={styles.protocolItem}>
              <span className={styles.protocolLabel}>Subsurface Depth Governance</span>
              <span className={styles.protocolVal}>
                Optical survey protocols govern surface defects only. Subsurface crack depth requires ultrasonic pulse velocity, impact echo, or ground-penetrating radar.
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

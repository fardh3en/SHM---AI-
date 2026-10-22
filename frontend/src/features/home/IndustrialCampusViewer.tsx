import { useState, useRef, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  CAMPUS_MARKERS,
  type CampusStructureMarker,
  type MonitoringMode,
} from './campus/industrialCampusData'
import {
  RotateCcw,
  Plus,
  Minus,
  Maximize2,
  Minimize2,
  Layers,
  Radio,
  AlertTriangle,
  ArrowRight,
} from 'lucide-react'
import styles from './IndustrialCampusViewer.module.css'

export default function IndustrialCampusViewer() {
  const containerRef = useRef<HTMLDivElement>(null)

  // Interactive modes
  const [activeMode, setActiveMode] = useState<MonitoringMode>('structure')
  const [selectedStructureId, setSelectedStructureId] = useState<string>('production_hall')

  // Pan & Zoom transform state
  const [zoomLevel, setZoomLevel] = useState<number>(1.0)
  const [panOffset, setPanOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 })
  const isDragging = useRef<boolean>(false)
  const dragStart = useRef<{ x: number; y: number }>({ x: 0, y: 0 })
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false)

  // Currently selected marker/structure
  const activeMarker: CampusStructureMarker =
    CAMPUS_MARKERS.find((m) => m.id === selectedStructureId) ?? CAMPUS_MARKERS[0]

  // Zoom handlers
  const handleZoomIn = () => {
    setZoomLevel((prev) => Math.min(prev + 0.25, 2.5))
  }

  const handleZoomOut = () => {
    setZoomLevel((prev) => Math.max(prev - 0.25, 1.0))
  }

  const handleResetView = () => {
    setZoomLevel(1.0)
    setPanOffset({ x: 0, y: 0 })
  }

  // Fullscreen toggle
  const toggleFullscreen = async () => {
    if (!containerRef.current) return

    if (!document.fullscreenElement) {
      try {
        await containerRef.current.requestFullscreen()
        setIsFullscreen(true)
      } catch {
        // Fallback if requestFullscreen fails
      }
    } else {
      try {
        await document.exitFullscreen()
        setIsFullscreen(false)
      } catch {
        // Fallback
      }
    }
  }

  useEffect(() => {
    const handleFsChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement))
    }
    document.addEventListener('fullscreenchange', handleFsChange)
    return () => document.removeEventListener('fullscreenchange', handleFsChange)
  }, [])

  // Drag pan handlers (active when zoomed in)
  const handlePointerDown = (e: React.PointerEvent) => {
    if (zoomLevel <= 1.0) return
    isDragging.current = true
    dragStart.current = {
      x: e.clientX - panOffset.x,
      y: e.clientY - panOffset.y,
    }
  }

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isDragging.current) return
    setPanOffset({
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y,
    })
  }

  const handlePointerUp = () => {
    isDragging.current = false
  }

  // Wheel zoom handler
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    if (e.deltaY < 0) {
      setZoomLevel((prev) => Math.min(prev + 0.15, 2.5))
    } else {
      setZoomLevel((prev) => {
        const next = Math.max(prev - 0.15, 1.0)
        if (next === 1.0) {
          setPanOffset({ x: 0, y: 0 })
        }
        return next
      })
    }
  }, [])

  return (
    <div
      ref={containerRef}
      className={styles.viewerContainer}
      role="region"
      aria-label="SHM-AI Industrial Monitoring Campus Digital Twin"
    >
      {/* Viewport Stage */}
      <div
        className={styles.viewportStage}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
        onWheel={handleWheel}
      >
        {/* Photorealistic High-Fidelity Digital Twin Image Layer */}
        <img
          src="/industrial-campus-twin.jpg"
          alt="SHM-AI Industrial Monitoring Campus Digital Twin"
          className={styles.canvasImageLayer}
          style={{
            transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomLevel})`,
          }}
          draggable={false}
        />

        {/* Cinematic Vignette Overlay */}
        <div className={styles.vignetteOverlay} />

        {/* Interactive Structural Markers Layer */}
        <div
          className={styles.markersContainer}
          style={{
            transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomLevel})`,
            transformOrigin: 'center center',
          }}
        >
          {CAMPUS_MARKERS.map((marker) => {
            const isSelected = selectedStructureId === marker.id

            // Label text conditioned on mode
            const subLabel =
              activeMode === 'monitoring'
                ? 'Active · Telemetry'
                : activeMode === 'defects'
                ? marker.latestFinding
                : marker.secondaryLabel

            return (
              <div
                key={marker.id}
                className={`${styles.markerAnchor} ${isSelected ? styles.markerAnchorActive : ''}`}
                style={{
                  top: marker.screenPos.top,
                  left: marker.screenPos.left,
                }}
                onClick={() => setSelectedStructureId(marker.id)}
                title={`Select ${marker.name} to view engineering dossier`}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    setSelectedStructureId(marker.id)
                  }
                }}
              >
                {/* Marker Head & Label */}
                <div
                  className={styles.markerHead}
                  style={{
                    flexDirection: marker.screenPos.labelPlacement === 'left' ? 'row-reverse' : 'row',
                  }}
                >
                  <div className={styles.targetDisc}>
                    <div
                      className={styles.targetDot}
                      style={{
                        backgroundColor:
                          activeMode === 'defects'
                            ? marker.statusType === 'attention' || marker.statusType === 'critical'
                              ? '#E0564A'
                              : '#D8C65A'
                            : '#D8C65A',
                      }}
                    />
                  </div>

                  <div className={styles.markerLabelBlock}>
                    <span className={styles.markerTitle}>{marker.name}</span>
                    <span className={styles.markerSub}>{subLabel}</span>
                  </div>
                </div>

                {/* Vertical Fine Leader Line */}
                <div
                  className={styles.leaderLine}
                  style={{ height: marker.screenPos.lineHeight }}
                />
                <div className={styles.leaderLineDot} />
              </div>
            )
          })}
        </div>
      </div>

      {/* Top-Left Segmented Control */}
      <div className={styles.topModeBar} role="toolbar" aria-label="Monitoring Mode Switcher">
        <div className={styles.segmentedControl}>
          <button
            type="button"
            className={`${styles.segmentBtn} ${activeMode === 'structure' ? styles.segmentBtnActive : ''}`}
            onClick={() => setActiveMode('structure')}
            aria-pressed={activeMode === 'structure'}
          >
            <Layers size={13} />
            <span>Structure</span>
          </button>

          <button
            type="button"
            className={`${styles.segmentBtn} ${activeMode === 'monitoring' ? styles.segmentBtnActive : ''}`}
            onClick={() => setActiveMode('monitoring')}
            aria-pressed={activeMode === 'monitoring'}
          >
            <Radio size={13} />
            <span>Monitoring</span>
          </button>

          <button
            type="button"
            className={`${styles.segmentBtn} ${activeMode === 'defects' ? styles.segmentBtnActive : ''}`}
            onClick={() => setActiveMode('defects')}
            aria-pressed={activeMode === 'defects'}
          >
            <AlertTriangle size={13} />
            <span>Defects</span>
          </button>
        </div>
      </div>

      {/* Top-Right Contextual Information Panel */}
      <aside className={styles.infoPanel} aria-label={`Inspection dossier for ${activeMarker.name}`}>
        <div className={styles.panelHeader}>
          <div className={styles.panelTitleArea}>
            <h4 className={styles.panelTitle}>{activeMarker.name}</h4>
            <span className={styles.panelCategory}>{activeMarker.category}</span>
          </div>
          <div className={styles.statusIndicatorTag}>
            <span className={styles.statusGreenDot} />
            <span>{activeMarker.statusText}</span>
          </div>
        </div>

        {/* Two-Column Finding Content */}
        <div className={styles.panelContentGrid}>
          <img
            src={activeMarker.crackImage}
            alt="High-resolution surface defect photographic evidence"
            className={styles.crackPhoto}
            loading="lazy"
          />

          <div className={styles.statsColumn}>
            <div className={styles.statRow}>
              <span className={styles.statLabel}>Latest Finding</span>
              <span className={styles.statValue}>{activeMarker.latestFinding}</span>
            </div>

            <div className={styles.statRow}>
              <span className={styles.statLabel}>Confidence</span>
              <span className={styles.statValue}>{activeMarker.confidence}</span>
            </div>

            <div className={styles.statRow}>
              <span className={styles.statLabel}>Length (px)</span>
              <span className={styles.statValue}>{activeMarker.lengthPx}</span>
            </div>

            <div className={styles.statRow}>
              <span className={styles.statLabel}>Status</span>
              <div className={styles.statusReviewBadge}>
                <span className={styles.reviewYellowDot} />
                <span>{activeMarker.findingStatus}</span>
              </div>
            </div>
          </div>
        </div>

        {/* View Details Action Button */}
        <Link
          to="/vision"
          className={styles.viewDetailsBtn}
          title={`Review detailed vision analysis and telemetry for ${activeMarker.name}`}
        >
          <span>View Details</span>
          <ArrowRight size={13} />
        </Link>
      </aside>

      {/* Bottom-Left Controls Bar */}
      <div className={styles.bottomLeftControls} role="toolbar" aria-label="Digital Twin Camera & Zoom Controls">
        <div className={styles.controlsBar}>
          <button
            type="button"
            className={styles.ctrlBtn}
            onClick={handleResetView}
            title="Reset viewport zoom and center framing"
          >
            <RotateCcw size={13} />
            <span>Reset View</span>
          </button>

          <div className={styles.ctrlDivider} />

          <button
            type="button"
            className={styles.ctrlBtn}
            onClick={handleZoomOut}
            title="Zoom out"
            aria-label="Zoom out"
          >
            <Minus size={13} />
          </button>

          <button
            type="button"
            className={styles.ctrlBtn}
            onClick={handleZoomIn}
            title="Zoom in"
            aria-label="Zoom in"
          >
            <Plus size={13} />
          </button>

          <button
            type="button"
            className={styles.ctrlBtn}
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
            aria-label={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
          >
            {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>
        </div>
      </div>

      {/* Bottom-Right Status Legend */}
      <div className={styles.bottomRightLegend} role="region" aria-label="Structural Health Status Legend">
        <div className={styles.legendBar}>
          <div className={styles.legendItem}>
            <span className={`${styles.legendDot} ${styles.dotMonitored}`} />
            <span>Monitored</span>
          </div>

          <div className={styles.legendItem}>
            <span className={`${styles.legendDot} ${styles.dotHealthy}`} />
            <span>Healthy</span>
          </div>

          <div className={styles.legendItem}>
            <span className={`${styles.legendDot} ${styles.dotAttention}`} />
            <span>Attention</span>
          </div>

          <div className={styles.legendItem}>
            <span className={`${styles.legendDot} ${styles.dotCritical}`} />
            <span>Critical</span>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * XRayBuildingViewer Component
 * Interactive real-time 3D structural X-Ray building digital twin matching Reference 1.
 * Features full-scene structural diagnostics, rebar reinforcement visualization,
 * branching 3D crack geometry with calibrated measurements, crack depth cutaway plane,
 * concrete deterioration & spalling zones, and engineering grid axes.
 */
import { useEffect, useRef, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import {
  RotateCcw,
  Layers,
  Box,
  Grid,
  AlertTriangle,
  ArrowRight,
  ChevronDown,
  Target,
  Scissors,
  Activity,
  ShieldAlert,
} from 'lucide-react'
import {
  BUILDING_MEMBERS,
  COLUMN_C03_DEFECT,
  type XRayViewingMode,
  type BuildingFloor,
  type StructuralMemberData,
} from './building/xrayBuildingData'
import { buildXRayBuilding } from './building/xrayBuildingBuilder'
import styles from './XRayBuildingViewer.module.css'

function checkWebGLSupport(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(
      window.WebGLRenderingContext &&
        (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
    )
  } catch {
    return false
  }
}

export default function XRayBuildingViewer() {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasMountRef = useRef<HTMLDivElement>(null)
  const tagCrackRef = useRef<HTMLDivElement>(null)
  const tagDepthRef = useRef<HTMLDivElement>(null)
  const tagRebarRef = useRef<HTMLDivElement>(null)

  const [webGLSupported, setWebGLSupported] = useState<boolean>(true)
  const [viewingMode, setViewingMode] = useState<XRayViewingMode>('xray') // Default: X-Ray
  const [selectedFloor, setSelectedFloor] = useState<BuildingFloor>('F2') // Default: F2
  const [selectedMemberId, setSelectedMemberId] = useState<string>('COL-C03') // Default: Column C-03
  const [isSectionCut, setIsSectionCut] = useState<boolean>(false)
  const [isLayersVisible, setIsLayersVisible] = useState<boolean>(true)

  // Full-scene diagnostic layer toggles
  const [showRebar, setShowRebar] = useState<boolean>(true)
  const [showDepthCut, setShowDepthCut] = useState<boolean>(true)
  const [showMetrics, setShowMetrics] = useState<boolean>(true)
  const [showDeterioration, setShowDeterioration] = useState<boolean>(true)

  // Three.js instances
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const controlsRef = useRef<OrbitControls | null>(null)
  const buildingResultRef = useRef<ReturnType<typeof buildXRayBuilding> | null>(null)
  const animFrameIdRef = useRef<number | null>(null)

  // Pointer drag vs click tracking
  const pointerDownPos = useRef<{ x: number; y: number }>({ x: 0, y: 0 })

  // Active selected member data
  const selectedMember: StructuralMemberData =
    BUILDING_MEMBERS[selectedMemberId] ?? BUILDING_MEMBERS['COL-C03']

  // ── Mode Switch Handler ────────────────────────────────────────────────────
  const handleModeChange = useCallback((mode: XRayViewingMode) => {
    setViewingMode(mode)
    if (buildingResultRef.current) {
      buildingResultRef.current.setViewingMode(mode)
    }
  }, [])

  // ── Floor Selection Handler ────────────────────────────────────────────────
  const handleFloorChange = useCallback((floor: BuildingFloor) => {
    setSelectedFloor(floor)
    if (buildingResultRef.current) {
      buildingResultRef.current.highlightFloor(floor)
    }
  }, [])

  // ── Camera & Tool Controls ─────────────────────────────────────────────────
  const handleResetView = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return
    cameraRef.current.position.set(24, 18, 24)
    controlsRef.current.target.set(0, 7.5, 0)
    controlsRef.current.update()
    handleModeChange('xray')
    setSelectedFloor('F2')
    setSelectedMemberId('COL-C03')
    setIsSectionCut(false)
    setIsLayersVisible(true)
    setShowRebar(true)
    setShowDepthCut(true)
    setShowMetrics(true)
    setShowDeterioration(true)
    if (buildingResultRef.current) {
      buildingResultRef.current.toggleSectionCut(false)
      buildingResultRef.current.toggleLayers(true)
      buildingResultRef.current.toggleRebar(true)
      buildingResultRef.current.toggleDepthCut(true)
      buildingResultRef.current.toggleDeterioration(true)
      buildingResultRef.current.highlightColumnC03(true)
    }
  }, [handleModeChange])

  const handleFocus = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return
    cameraRef.current.position.set(11, 10, 13)
    controlsRef.current.target.set(3, 8.7, 7)
    controlsRef.current.update()
  }, [])

  const handleToggleSection = useCallback(() => {
    setIsSectionCut((prev) => {
      const next = !prev
      if (buildingResultRef.current) {
        buildingResultRef.current.toggleSectionCut(next)
      }
      return next
    })
  }, [])

  const handleToggleLayers = useCallback(() => {
    setIsLayersVisible((prev) => {
      const next = !prev
      if (buildingResultRef.current) {
        buildingResultRef.current.toggleLayers(next)
      }
      return next
    })
  }, [])

  // ── Diagnostic HUD Toggles ─────────────────────────────────────────────────
  const handleToggleRebar = useCallback(() => {
    setShowRebar((prev) => {
      const next = !prev
      buildingResultRef.current?.toggleRebar(next)
      return next
    })
  }, [])

  const handleToggleDepthCut = useCallback(() => {
    setShowDepthCut((prev) => {
      const next = !prev
      buildingResultRef.current?.toggleDepthCut(next)
      return next
    })
  }, [])

  const handleToggleMetrics = useCallback(() => {
    setShowMetrics((prev) => !prev)
  }, [])

  const handleToggleDeterioration = useCallback(() => {
    setShowDeterioration((prev) => {
      const next = !prev
      buildingResultRef.current?.toggleDeterioration(next)
      return next
    })
  }, [])

  // ── Three.js Lifecycle Setup ───────────────────────────────────────────────
  useEffect(() => {
    if (!checkWebGLSupport()) {
      setWebGLSupported(false)
      return
    }

    const mount = canvasMountRef.current
    if (!mount) return

    const width = mount.clientWidth || 800
    const height = mount.clientHeight || 580

    // Scene with deep charcoal background matching Reference 1
    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#151514')
    scene.fog = new THREE.FogExp2('#151514', 0.009)
    sceneRef.current = scene

    // Camera at elevated isometric 3/4 perspective
    const camera = new THREE.PerspectiveCamera(38, width / height, 0.5, 450)
    camera.position.set(24, 18, 24)
    cameraRef.current = camera

    // WebGL Renderer
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        powerPreference: 'high-performance',
      })
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
      renderer.setSize(width, height)
      renderer.shadowMap.enabled = true
      renderer.shadowMap.type = THREE.PCFSoftShadowMap
      renderer.toneMapping = THREE.ACESFilmicToneMapping
      renderer.toneMappingExposure = 1.25
      mount.appendChild(renderer.domElement)
      rendererRef.current = renderer
    } catch {
      setWebGLSupported(false)
      return
    }

    // OrbitControls
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.06
    controls.minDistance = 6
    controls.maxDistance = 85
    controls.maxPolarAngle = Math.PI * 0.49
    controls.target.set(0, 7.5, 0)
    controls.autoRotate = false
    controlsRef.current = controls

    // ── Studio Lighting Rig ──────────────────────────────────────────────────
    const ambientLight = new THREE.AmbientLight('#E5E2D8', 0.75)
    scene.add(ambientLight)

    const keyLight = new THREE.DirectionalLight('#FFFBE8', 1.35)
    keyLight.position.set(25, 38, 22)
    keyLight.castShadow = true
    keyLight.shadow.mapSize.width = 1024
    keyLight.shadow.mapSize.height = 1024
    keyLight.shadow.camera.near = 1
    keyLight.shadow.camera.far = 120
    const d = 20
    keyLight.shadow.camera.left = -d
    keyLight.shadow.camera.right = d
    keyLight.shadow.camera.top = d
    keyLight.shadow.camera.bottom = -d
    keyLight.shadow.bias = -0.0004
    scene.add(keyLight)

    const fillLight = new THREE.DirectionalLight('#A0A6B2', 0.5)
    fillLight.position.set(-24, 18, -18)
    scene.add(fillLight)

    const bounceLight = new THREE.DirectionalLight('#3A3830', 0.25)
    bounceLight.position.set(0, -10, 0)
    scene.add(bounceLight)

    // ── Procedural Building Geometry ─────────────────────────────────────────
    const buildingResult = buildXRayBuilding()
    scene.add(buildingResult.rootGroup)
    buildingResultRef.current = buildingResult

    buildingResult.setViewingMode('xray')
    buildingResult.highlightFloor('F2')

    // Raycaster for interactive component clicking
    const raycaster = new THREE.Raycaster()
    const mouse = new THREE.Vector2()

    const handlePointerDown = (e: PointerEvent) => {
      pointerDownPos.current = { x: e.clientX, y: e.clientY }
    }

    const handlePointerUp = (e: PointerEvent) => {
      const dx = Math.abs(e.clientX - pointerDownPos.current.x)
      const dy = Math.abs(e.clientY - pointerDownPos.current.y)
      if (dx < 6 && dy < 6) {
        const rect = renderer.domElement.getBoundingClientRect()
        mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
        mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1

        raycaster.setFromCamera(mouse, camera)
        const intersects = raycaster.intersectObjects(
          buildingResult.interactiveMeshes,
          true
        )

        if (intersects.length > 0) {
          const hit = intersects[0].object
          const memberId = hit.userData?.memberId
          if (memberId && BUILDING_MEMBERS[memberId]) {
            setSelectedMemberId(memberId)
          }
        }
      }
    }

    const domElement = renderer.domElement
    domElement.addEventListener('pointerdown', handlePointerDown)
    domElement.addEventListener('pointerup', handlePointerUp)

    // Projection vector for 3D-to-2D screen coordinate callouts
    const pVec = new THREE.Vector3()

    // ── Render Loop ──────────────────────────────────────────────────────────
    let isRunning = true
    const animate = () => {
      if (!isRunning) return
      animFrameIdRef.current = requestAnimationFrame(animate)

      controls.update()
      renderer.render(scene, camera)

      // Project spatial diagnostic callouts over Column C-03
      const cWidth = mount.clientWidth
      const cHeight = mount.clientHeight

      // 1. Crack surface callout at (3.05, 9.4, 7.36)
      if (tagCrackRef.current) {
        pVec.set(3.05, 9.4, 7.36).project(camera)
        if (pVec.z < 1.0) {
          const sx = (pVec.x * 0.5 + 0.5) * cWidth
          const sy = (-(pVec.y * 0.5) + 0.5) * cHeight
          tagCrackRef.current.style.transform = `translate3d(${sx}px, ${sy}px, 0) translate(-50%, -100%)`
          tagCrackRef.current.style.display = 'inline-flex'
        } else {
          tagCrackRef.current.style.display = 'none'
        }
      }

      // 2. Depth cutaway callout at (3.25, 8.4, 7.36)
      if (tagDepthRef.current) {
        pVec.set(3.25, 8.4, 7.36).project(camera)
        if (pVec.z < 1.0) {
          const sx = (pVec.x * 0.5 + 0.5) * cWidth
          const sy = (-(pVec.y * 0.5) + 0.5) * cHeight
          tagDepthRef.current.style.transform = `translate3d(${sx}px, ${sy}px, 0) translate(-50%, -100%)`
          tagDepthRef.current.style.display = 'inline-flex'
        } else {
          tagDepthRef.current.style.display = 'none'
        }
      }

      // 3. Rebar cage callout at (2.6, 7.7, 7.36)
      if (tagRebarRef.current) {
        pVec.set(2.6, 7.7, 7.36).project(camera)
        if (pVec.z < 1.0) {
          const sx = (pVec.x * 0.5 + 0.5) * cWidth
          const sy = (-(pVec.y * 0.5) + 0.5) * cHeight
          tagRebarRef.current.style.transform = `translate3d(${sx}px, ${sy}px, 0) translate(-50%, -100%)`
          tagRebarRef.current.style.display = 'inline-flex'
        } else {
          tagRebarRef.current.style.display = 'none'
        }
      }
    }
    animate()

    // ── Resize Observer ──────────────────────────────────────────────────────
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width: newWidth, height: newHeight } = entry.contentRect
        if (newWidth > 0 && newHeight > 0) {
          camera.aspect = newWidth / newHeight
          camera.updateProjectionMatrix()
          renderer.setSize(newWidth, newHeight)
        }
      }
    })
    resizeObserver.observe(mount)

    // ── Cleanup ──────────────────────────────────────────────────────────────
    return () => {
      isRunning = false
      if (animFrameIdRef.current !== null) {
        cancelAnimationFrame(animFrameIdRef.current)
      }
      resizeObserver.disconnect()
      domElement.removeEventListener('pointerdown', handlePointerDown)
      domElement.removeEventListener('pointerup', handlePointerUp)

      buildingResult.cleanup()
      controls.dispose()
      renderer.dispose()

      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement)
      }
    }
  }, [])

  if (!webGLSupported) {
    return (
      <div className={styles.fallbackContainer}>
        <AlertTriangle size={32} color="#D8C65A" style={{ marginBottom: 12 }} />
        <h2 className={styles.fallbackTitle}>WebGL Hardware Acceleration Required</h2>
        <p className={styles.fallbackText}>
          Your browser does not have WebGL enabled. Please enable hardware acceleration to
          explore the real-time 3D structural X-Ray building twin.
        </p>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className={styles.viewerContainer}
      role="region"
      aria-label="SHM-AI Interactive 3D X-Ray Building Digital Twin"
    >
      {/* 3D Canvas Mount */}
      <div ref={canvasMountRef} className={styles.canvasStage} />

      {/* Subtle Depth Vignette */}
      <div className={styles.vignetteOverlay} />

      {/* ── Mode Selector: Vertical Floating Stack (Top Left) ───────────────── */}
      <nav className={styles.modeSelector} aria-label="Building Visualization Modes">
        <button
          type="button"
          className={`${styles.modeBtn} ${
            viewingMode === 'exterior' ? styles.modeBtnActive : ''
          }`}
          onClick={() => handleModeChange('exterior')}
        >
          <Box size={15} />
          Exterior
        </button>

        <button
          type="button"
          className={`${styles.modeBtn} ${
            viewingMode === 'xray' ? styles.modeBtnActive : ''
          }`}
          onClick={() => handleModeChange('xray')}
        >
          <Layers size={15} />
          X-Ray
        </button>

        <button
          type="button"
          className={`${styles.modeBtn} ${
            viewingMode === 'structure' ? styles.modeBtnActive : ''
          }`}
          onClick={() => handleModeChange('structure')}
        >
          <Grid size={15} />
          Structure
        </button>

        <button
          type="button"
          className={`${styles.modeBtn} ${
            viewingMode === 'defects' ? styles.modeBtnActive : ''
          }`}
          onClick={() => handleModeChange('defects')}
        >
          <AlertTriangle size={15} />
          Defects
        </button>
      </nav>

      {/* ── Top-Center: Full-Scene Diagnostic Layer Toggles HUD ──────────────── */}
      <div className={styles.hudLayerBar} role="toolbar" aria-label="Diagnostic Layers">
        <button
          type="button"
          className={`${styles.hudPillBtn} ${showRebar ? styles.hudPillBtnActive : ''}`}
          onClick={handleToggleRebar}
          title="Toggle Rebar Cage Visualization"
        >
          <span className={styles.hudDot} />
          Rebar Cage
        </button>

        <button
          type="button"
          className={`${styles.hudPillBtn} ${showDepthCut ? styles.hudPillBtnActive : ''}`}
          onClick={handleToggleDepthCut}
          title="Toggle Crack Depth Penetration Slice"
        >
          <span className={styles.hudDot} />
          Crack Depth (28mm)
        </button>

        <button
          type="button"
          className={`${styles.hudPillBtn} ${showMetrics ? styles.hudPillBtnActive : ''}`}
          onClick={handleToggleMetrics}
          title="Toggle 3D Spatial Metrics Callouts"
        >
          <span className={styles.hudDot} />
          Spatial Metrics
        </button>

        <button
          type="button"
          className={`${styles.hudPillBtn} ${showDeterioration ? styles.hudPillBtnActive : ''}`}
          onClick={handleToggleDeterioration}
          title="Toggle Deterioration & Spall Zones"
        >
          <span className={styles.hudDot} />
          Deterioration
        </button>
      </div>

      {/* ── Top-Right: Mini Building Preview Card ────────────────────────────── */}
      <div className={styles.buildingPreviewCard}>
        <div className={styles.previewHeader}>
          <span>Building A</span>
          <ChevronDown size={14} color="#85896F" />
        </div>
        <div className={styles.previewGraphic}>
          <svg className={styles.miniBuildingSvg} viewBox="0 0 100 50">
            <polygon points="50,42 90,26 50,14 10,26" fill="#242220" stroke="#414039" strokeWidth="0.8" />
            <polygon points="50,14 80,24 80,4 50,-4" fill="#383632" opacity="0.6" stroke="#55534a" strokeWidth="0.6" />
            <polygon points="50,14 20,24 20,4 50,-4" fill="#2c2a26" opacity="0.6" stroke="#55534a" strokeWidth="0.6" />
            <rect x="58" y="6" width="6" height="20" fill="#D8C65A" opacity="0.9" rx="1" />
          </svg>
        </div>
      </div>

      {/* ── Screen-Space Projected Hotspots & Depth Tags ─────────────────────── */}
      {showMetrics && (
        <div className={styles.pinsOverlay}>
          {/* Tag 1: Surface Crack Metrics */}
          <div ref={tagCrackRef} className={styles.spatialCalloutTag}>
            <Activity size={12} />
            <span>Crack: 184 mm · Width: 0.8 mm</span>
          </div>

          {/* Tag 2: Depth Cutaway & Cover Penetration */}
          <div ref={tagDepthRef} className={`${styles.spatialCalloutTag} ${styles.spatialTagAmber}`}>
            <ShieldAlert size={12} />
            <span>Depth: 28 mm · Cover: 40 mm</span>
          </div>

          {/* Tag 3: Rebar Reinforcement Arrangement */}
          <div ref={tagRebarRef} className={`${styles.spatialCalloutTag} ${styles.spatialTagCyan}`}>
            <Grid size={12} />
            <span>Rebar: 8×Ø28mm · Clearance: 12mm</span>
          </div>
        </div>
      )}

      {/* ── Floating Diagnostic Card: Column C-03 (Reference 1) ─────────────── */}
      <aside
        className={styles.diagnosticCard}
        aria-label={`Structural diagnostic for ${selectedMember.name}`}
      >
        <div className={styles.cardHeader}>
          <div className={styles.cardTitleBlock}>
            <span className={styles.cardIdTag}>{COLUMN_C03_DEFECT.crackId}</span>
            <span className={styles.cardTitle}>{selectedMember.name}</span>
          </div>
          <Link
            to="/vision"
            className={styles.cardArrowLink}
            title="Inspect Component Findings in Vision Studio"
            aria-label="Inspect Component Findings in Vision Studio"
          >
            <ArrowRight size={15} />
          </Link>
        </div>

        <div className={styles.cardBody}>
          <div className={styles.thumbContainer}>
            <img
              src={selectedMember.crackImage || '/crack-detail.jpg'}
              alt={`${selectedMember.name} Surface Crack`}
              className={styles.thumbImg}
            />
            <span className={styles.thumbOverlayTag}>
              {selectedMember.latestFinding || 'Surface Crack'}
            </span>
          </div>

          <div className={styles.metricsCol}>
            <div className={styles.metricRow}>
              <span className={styles.metricName}>Length (3D)</span>
              <span className={styles.metricHighlight}>{COLUMN_C03_DEFECT.lengthMm} mm</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricName}>Width (max)</span>
              <span className={styles.metricHighlight}>{COLUMN_C03_DEFECT.maxWidthMm} mm</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricName}>Depth (slice)</span>
              <span className={styles.metricDepthAmber}>
                {COLUMN_C03_DEFECT.crackDepthMm} mm / {COLUMN_C03_DEFECT.concreteCoverMm} mm
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricName}>Rebar Gap</span>
              <span className={styles.metricVal}>{COLUMN_C03_DEFECT.rebarClearanceMm} mm</span>
            </div>
            <div className={styles.metricRow}>
              <span className={styles.metricName}>Confidence</span>
              <span className={styles.metricVal}>94% (UPV)</span>
            </div>
          </div>
        </div>

        {/* Engineering Directive Banner */}
        <div className={styles.cardDirectiveBox}>
          <strong>NDT Directive:</strong> Carbonation ingress 22mm. Apply epoxy-resin micro-injection within 30 days.
        </div>
      </aside>

      {/* ── Far-Right: Vertical Floor Selector (Reference 1) ────────────────── */}
      <nav className={styles.floorSelector} aria-label="Floor Selector">
        {(['Roof', 'F4', 'F3', 'F2', 'F1', 'GF'] as BuildingFloor[]).map((floor) => (
          <button
            key={floor}
            type="button"
            className={`${styles.floorBtn} ${
              selectedFloor === floor ? styles.floorBtnActive : ''
            }`}
            onClick={() => handleFloorChange(floor)}
          >
            {floor}
          </button>
        ))}
      </nav>

      {/* ── Bottom Toolbar: Horizontal Pill (Bottom Center) ─────────────────── */}
      <div className={styles.bottomToolbar} role="toolbar" aria-label="3D Viewport Controls">
        <button
          type="button"
          className={styles.toolBtn}
          onClick={handleResetView}
          title="Reset View"
        >
          <RotateCcw size={14} />
          Reset
        </button>

        <div className={styles.toolDivider} />

        <button
          type="button"
          className={styles.toolBtn}
          onClick={handleFocus}
          title="Focus Column C-03"
        >
          <Target size={14} />
          Focus
        </button>

        <div className={styles.toolDivider} />

        <button
          type="button"
          className={`${styles.toolBtn} ${isSectionCut ? styles.toolBtnActive : ''}`}
          onClick={handleToggleSection}
          title="Toggle Section Cutaway"
        >
          <Scissors size={14} />
          Section
        </button>

        <div className={styles.toolDivider} />

        <button
          type="button"
          className={`${styles.toolBtn} ${!isLayersVisible ? styles.toolBtnActive : ''}`}
          onClick={handleToggleLayers}
          title="Toggle Structural Layers"
        >
          <Layers size={14} />
          Layers
        </button>
      </div>
    </div>
  )
}

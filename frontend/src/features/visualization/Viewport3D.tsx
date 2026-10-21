import { useEffect, useRef, useState, useCallback } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { Asset } from '../../api/assets'
import type { Inspection } from '../../api/inspections'
import type { StructuralComponentData } from './models/types'
import { buildStructuralModel } from './models/modelFactory'
import {
  RotateCcw,
  Eye,
  Maximize2,
  Minimize2,
  Compass,
  Grid,
  AlertTriangle,
  Layers,
} from 'lucide-react'
import styles from './Viewport3D.module.css'

interface Viewport3DProps {
  asset: Asset
  inspections?: Inspection[]
  selectedComponentId: string | null
  onSelectComponent: (component: StructuralComponentData | null) => void
}

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

export default function Viewport3D({
  asset,
  inspections = [],
  selectedComponentId,
  onSelectComponent,
}: Viewport3DProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [webGLSupported, setWebGLSupported] = useState(true)
  const [modelType, setModelType] = useState<string>('Bridge Structure')
  const [isWireframe, setIsWireframe] = useState(false)
  const [isAutoRotate, setIsAutoRotate] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [hoveredName, setHoveredName] = useState<string | null>(null)

  // Three.js internal references
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const controlsRef = useRef<OrbitControls | null>(null)
  const modelGroupRef = useRef<THREE.Group | null>(null)
  const componentsMapRef = useRef<Map<string, StructuralComponentData>>(new Map())
  const highlightBoxRef = useRef<THREE.BoxHelper | null>(null)
  const animFrameIdRef = useRef<number | null>(null)

  // Track pointer down coordinate to distinguish drag from click
  const pointerDownPos = useRef<{ x: number; y: number }>({ x: 0, y: 0 })

  // Initialize Three.js scene once
  useEffect(() => {
    if (!checkWebGLSupport()) {
      setWebGLSupported(false)
      return
    }

    const container = containerRef.current
    if (!container) return

    // Create scene
    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#171715')
    scene.fog = new THREE.FogExp2('#171715', 0.012)
    sceneRef.current = scene

    // Camera
    const width = container.clientWidth || 800
    const height = container.clientHeight || 540
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.5, 500)
    camera.position.set(0, 14, 28)
    cameraRef.current = camera

    // Renderer
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
      renderer.toneMappingExposure = 1.05
      container.appendChild(renderer.domElement)
      rendererRef.current = renderer
    } catch {
      setWebGLSupported(false)
      return
    }

    // OrbitControls
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.08
    controls.minDistance = 3
    controls.maxDistance = 120
    controls.maxPolarAngle = Math.PI * 0.88
    controls.target.set(0, 2.5, 0)
    controlsRef.current = controls

    // Ambient light
    const ambientLight = new THREE.AmbientLight('#E8E6DF', 0.6)
    scene.add(ambientLight)

    // Directional Key Light
    const keyLight = new THREE.DirectionalLight('#FFFBEB', 1.0)
    keyLight.position.set(20, 32, 22)
    keyLight.castShadow = true
    keyLight.shadow.mapSize.width = 1024
    keyLight.shadow.mapSize.height = 1024
    keyLight.shadow.camera.near = 1
    keyLight.shadow.camera.far = 100
    const d = 25
    keyLight.shadow.camera.left = -d
    keyLight.shadow.camera.right = d
    keyLight.shadow.camera.top = d
    keyLight.shadow.camera.bottom = -d
    keyLight.shadow.bias = -0.0005
    scene.add(keyLight)

    // Directional Fill / Rim Light
    const fillLight = new THREE.DirectionalLight('#9FA8A3', 0.45)
    fillLight.position.set(-22, 16, -18)
    scene.add(fillLight)

    // Under / Bounce Light
    const bounceLight = new THREE.DirectionalLight('#3A3830', 0.25)
    bounceLight.position.set(0, -10, 0)
    scene.add(bounceLight)

    // Grid floor
    const grid = new THREE.GridHelper(70, 70, '#3A3830', '#22221F')
    grid.position.y = -0.05
    scene.add(grid)

    // Render loop
    const animate = () => {
      animFrameIdRef.current = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    // Resize observer
    const handleResize = () => {
      if (!container || !rendererRef.current || !cameraRef.current) return
      const w = container.clientWidth
      const h = container.clientHeight
      cameraRef.current.aspect = w / h
      cameraRef.current.updateProjectionMatrix()
      rendererRef.current.setSize(w, h)
    }

    const resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(container)

    return () => {
      if (animFrameIdRef.current) {
        cancelAnimationFrame(animFrameIdRef.current)
      }
      resizeObserver.disconnect()
      controls.dispose()
      renderer.dispose()
      if (renderer.domElement.parentElement === container) {
        container.removeChild(renderer.domElement)
      }
    }
  }, [])

  // Rebuild procedural model when asset or inspections change
  useEffect(() => {
    const scene = sceneRef.current
    if (!scene) return

    // Remove existing model group
    if (modelGroupRef.current) {
      scene.remove(modelGroupRef.current)
      modelGroupRef.current.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.geometry?.dispose()
          if (Array.isArray(child.material)) {
            child.material.forEach((m) => m.dispose())
          } else {
            child.material?.dispose()
          }
        }
      })
      modelGroupRef.current = null
    }

    // Remove highlight box if any
    if (highlightBoxRef.current) {
      scene.remove(highlightBoxRef.current)
      highlightBoxRef.current.dispose()
      highlightBoxRef.current = null
    }

    // Build new parametric model
    const buildResult = buildStructuralModel(asset, inspections)
    scene.add(buildResult.group)
    modelGroupRef.current = buildResult.group
    componentsMapRef.current = buildResult.components
    setModelType(buildResult.modelType)

    // Reset controls target
    if (controlsRef.current && cameraRef.current) {
      controlsRef.current.target.set(0, 2.5, 0)
      controlsRef.current.update()
    }
  }, [asset, inspections])

  // Update wireframe mode
  useEffect(() => {
    if (!modelGroupRef.current) return
    modelGroupRef.current.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        if (Array.isArray(child.material)) {
          child.material.forEach((m) => {
            if ('wireframe' in m) (m as THREE.MeshStandardMaterial).wireframe = isWireframe
          })
        } else if ('wireframe' in child.material) {
          (child.material as THREE.MeshStandardMaterial).wireframe = isWireframe
        }
      }
    })
  }, [isWireframe])

  // Update auto rotate
  useEffect(() => {
    if (!controlsRef.current) return
    controlsRef.current.autoRotate = isAutoRotate
    controlsRef.current.autoRotateSpeed = 0.5
  }, [isAutoRotate])

  // Update selection highlight box
  useEffect(() => {
    const scene = sceneRef.current
    if (!scene) return

    // Remove old highlight box
    if (highlightBoxRef.current) {
      scene.remove(highlightBoxRef.current)
      highlightBoxRef.current.dispose()
      highlightBoxRef.current = null
    }

    if (!selectedComponentId || !modelGroupRef.current) return

    // Find the mesh with matching userData.id
    let targetMesh: THREE.Mesh | null = null
    modelGroupRef.current.traverse((child) => {
      if (child instanceof THREE.Mesh && child.userData?.id === selectedComponentId) {
        targetMesh = child
      }
    })

    if (targetMesh) {
      // Create a highlight box around the mesh
      const box = new THREE.BoxHelper(targetMesh, 0xd8c65a)
      const boxMat = box.material as THREE.LineBasicMaterial
      boxMat.linewidth = 2
      boxMat.depthTest = false
      boxMat.transparent = true
      boxMat.opacity = 0.95
      scene.add(box)
      highlightBoxRef.current = box
    }
  }, [selectedComponentId])

  // Handle pointer down (to distinguish clicks from camera rotation)
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    pointerDownPos.current = { x: e.clientX, y: e.clientY }
  }

  // Handle pointer click for raycasting selection
  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    const dx = Math.abs(e.clientX - pointerDownPos.current.x)
    const dy = Math.abs(e.clientY - pointerDownPos.current.y)
    // If user dragged more than 5px, it was a camera orbit/pan, not a click
    if (dx > 5 || dy > 5) return

    const container = containerRef.current
    const camera = cameraRef.current
    const modelGroup = modelGroupRef.current
    if (!container || !camera || !modelGroup) return

    const rect = container.getBoundingClientRect()
    const mouse = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1
    )

    const raycaster = new THREE.Raycaster()
    raycaster.setFromCamera(mouse, camera)

    const intersects = raycaster.intersectObjects(modelGroup.children, true)
    let selectedComp: StructuralComponentData | null = null

    for (const hit of intersects) {
      if (hit.object.userData && hit.object.userData.id) {
        selectedComp = hit.object.userData as StructuralComponentData
        break
      }
    }

    onSelectComponent(selectedComp)
  }

  // Handle pointer move to update hover cursor and component label
  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const container = containerRef.current
    const camera = cameraRef.current
    const modelGroup = modelGroupRef.current
    if (!container || !camera || !modelGroup) return

    const rect = container.getBoundingClientRect()
    const mouse = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1
    )

    const raycaster = new THREE.Raycaster()
    raycaster.setFromCamera(mouse, camera)

    const intersects = raycaster.intersectObjects(modelGroup.children, true)
    let hitName: string | null = null

    for (const hit of intersects) {
      if (hit.object.userData && hit.object.userData.name) {
        hitName = hit.object.userData.name
        break
      }
    }

    if (hitName) {
      container.style.cursor = 'pointer'
      setHoveredName(hitName)
    } else {
      container.style.cursor = 'default'
      setHoveredName(null)
    }
  }

  // Camera presets
  const applyCameraPreset = useCallback(
    (preset: 'isometric' | 'top' | 'side' | 'front') => {
      const camera = cameraRef.current
      const controls = controlsRef.current
      if (!camera || !controls) return

      switch (preset) {
        case 'isometric':
          camera.position.set(0, 14, 28)
          controls.target.set(0, 2.5, 0)
          break
        case 'top':
          camera.position.set(0, 36, 0.01)
          controls.target.set(0, 0, 0)
          break
        case 'side':
          camera.position.set(34, 4, 0)
          controls.target.set(0, 2.5, 0)
          break
        case 'front':
          camera.position.set(0, 4, 34)
          controls.target.set(0, 2.5, 0)
          break
      }
      controls.update()
    },
    []
  )

  const toggleFullscreen = () => {
    const container = containerRef.current
    if (!container) return
    if (!document.fullscreenElement) {
      container.requestFullscreen?.().catch(() => {})
      setIsFullscreen(true)
    } else {
      document.exitFullscreen?.().catch(() => {})
      setIsFullscreen(false)
    }
  }

  const selectedData = selectedComponentId
    ? componentsMapRef.current.get(selectedComponentId)
    : null

  if (!webGLSupported) {
    return (
      <div className={styles.fallbackContainer} role="region" aria-label="3D Viewport Fallback">
        <AlertTriangle size={36} color="#D8C65A" />
        <h3 className={styles.fallbackTitle}>3D WebGL Acceleration Unavailable</h3>
        <p className={styles.fallbackText}>
          Your browser or graphics environment does not support WebGL hardware acceleration.
          Please enable hardware acceleration in your browser settings or use a WebGL-compatible
          system to interact with the 3D structural model.
        </p>
      </div>
    )
  }

  return (
    <div
      className={styles.viewportContainer}
      ref={containerRef}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerMove={handlePointerMove}
      role="region"
      aria-label={`Interactive 3D model of ${asset.name}`}
    >
      {/* Top-Left Indicator Badge */}
      <div className={styles.hudBadgeTopLeft}>
        <span className={styles.badgeIconPulse} />
        <span className={styles.badgeType}>{modelType}</span>
        <span className={styles.badgeDisclaimer}>• Parametric Engineering Reference</span>
      </div>

      {/* Top-Right Selection / Hover HUD Info */}
      {(selectedData || hoveredName) && (
        <div className={styles.hudSelectionInfo} aria-live="polite">
          <span
            className={`${styles.selectionIndicator} ${
              selectedData?.status === 'assessed_findings'
                ? styles.statusFinding
                : selectedData?.status === 'assessed_nominal'
                ? styles.statusNominal
                : styles.statusUnassessed
            }`}
          />
          <span>{selectedData ? selectedData.name : hoveredName}</span>
        </div>
      )}

      {/* Subtle Hint */}
      {!selectedComponentId && (
        <div className={styles.interactionHint}>
          Click any structural member or pier to inspect details & linked findings
        </div>
      )}

      {/* Bottom Floating HUD Toolbar */}
      <div className={styles.hudToolbar} role="toolbar" aria-label="3D Camera & View Controls">
        <div className={styles.hudGroup}>
          <button
            type="button"
            className={styles.hudButton}
            onClick={() => applyCameraPreset('isometric')}
            title="Reset to Isometric Overview"
          >
            <RotateCcw size={13} />
            <span>Overview</span>
          </button>
          <button
            type="button"
            className={styles.hudButton}
            onClick={() => applyCameraPreset('top')}
            title="Top-Down Plan View"
          >
            <Compass size={13} />
            <span>Plan</span>
          </button>
          <button
            type="button"
            className={styles.hudButton}
            onClick={() => applyCameraPreset('side')}
            title="Side Profile Elevation"
          >
            <Eye size={13} />
            <span>Side</span>
          </button>
          <button
            type="button"
            className={styles.hudButton}
            onClick={() => applyCameraPreset('front')}
            title="Front Elevation"
          >
            <Layers size={13} />
            <span>Front</span>
          </button>
        </div>

        <div className={styles.hudDivider} />

        <div className={styles.hudGroup}>
          <button
            type="button"
            className={`${styles.hudButton} ${isWireframe ? styles.hudButtonActive : ''}`}
            onClick={() => setIsWireframe((prev) => !prev)}
            title="Toggle Wireframe Structural Framework"
            aria-pressed={isWireframe}
          >
            <Grid size={13} />
            <span>Wireframe</span>
          </button>
          <button
            type="button"
            className={`${styles.hudButton} ${isAutoRotate ? styles.hudButtonActive : ''}`}
            onClick={() => setIsAutoRotate((prev) => !prev)}
            title="Toggle Continuous Orbit Rotation"
            aria-pressed={isAutoRotate}
          >
            <RotateCcw size={13} />
            <span>Rotate</span>
          </button>
          <button
            type="button"
            className={styles.hudButton}
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen 3D View'}
            aria-label={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen 3D View'}
          >
            {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>
        </div>
      </div>
    </div>
  )
}

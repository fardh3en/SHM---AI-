/**
 * Industrial Campus Procedural Model Builder
 * Constructs a real-time, lightweight, high-fidelity 3D architectural digital twin
 * representing an entire industrial monitoring campus.
 */
import * as THREE from 'three'
import { CAMPUS_MARKERS } from './industrialCampusData'

export interface CampusBuildResult {
  rootGroup: THREE.Group
  facilitiesMap: Map<string, THREE.Group>
  sensorMarkersMap: Map<string, THREE.Mesh>
  defectMarkersMap: Map<string, THREE.Mesh>
  interactiveMeshes: THREE.Mesh[]
  cleanup: () => void
}

export function buildIndustrialCampus(): CampusBuildResult {
  const rootGroup = new THREE.Group()
  const facilitiesMap = new Map<string, THREE.Group>()
  const sensorMarkersMap = new Map<string, THREE.Mesh>()
  const defectMarkersMap = new Map<string, THREE.Mesh>()
  const interactiveMeshes: THREE.Mesh[] = []

  // Shared Geometries (for high performance and low draw calls)
  const geometriesToDispose: THREE.BufferGeometry[] = []
  const materialsToDispose: THREE.Material[] = []

  const trackGeo = <T extends THREE.BufferGeometry>(g: T): T => {
    geometriesToDispose.push(g)
    return g
  }

  const trackMat = <T extends THREE.Material>(m: T): T => {
    materialsToDispose.push(m)
    return m
  }

  // ── Palette & PBR Materials ────────────────────────────────────────────────
  const matGround = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#1a181b', // Deep charcoal base matching hero plum tones
      roughness: 0.9,
      metalness: 0.1,
    })
  )

  const matPaving = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#282624',
      roughness: 0.85,
      metalness: 0.15,
    })
  )

  const matRoad = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#1f1e1c',
      roughness: 0.7,
      metalness: 0.2,
    })
  )

  const matRoadLine = trackMat(
    new THREE.MeshBasicMaterial({
      color: '#D8C65A',
      transparent: true,
      opacity: 0.65,
    })
  )

  const matGrass = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#3d4436', // Restrained desaturated olive green
      roughness: 0.95,
      metalness: 0.05,
    })
  )

  const matConcrete = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#5a5752',
      roughness: 0.8,
      metalness: 0.15,
    })
  )

  const matLightConcrete = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#7a766e',
      roughness: 0.7,
      metalness: 0.2,
    })
  )

  const matDarkSteel = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#2b2a28',
      roughness: 0.45,
      metalness: 0.6,
    })
  )

  const matBrightSteel = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#828078',
      roughness: 0.35,
      metalness: 0.7,
    })
  )

  const matGlass = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#2a3338',
      roughness: 0.15,
      metalness: 0.85,
      transparent: true,
      opacity: 0.82,
    })
  )

  const matSensorGlow = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#D8C65A', // Mineral Yellow
      emissive: '#D8C65A',
      emissiveIntensity: 0.8,
      roughness: 0.2,
      metalness: 0.4,
    })
  )

  const matDefectGlow = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#E0564A', // Crimson Warning
      emissive: '#E0564A',
      emissiveIntensity: 0.85,
      roughness: 0.2,
      metalness: 0.4,
    })
  )

  // Helper to add interactive meshes to hit-testing array and tag them
  const registerInteractiveMesh = (
    mesh: THREE.Mesh,
    assetId: string,
    componentName: string
  ) => {
    mesh.castShadow = true
    mesh.receiveShadow = true
    mesh.userData = {
      isCampusAsset: true,
      assetId,
      componentName,
    }
    interactiveMeshes.push(mesh)
  }

  // ── 1. Base Plinth & Ground Infrastructure ─────────────────────────────────
  const baseGroup = new THREE.Group()

  // Main Plinth
  const plinthGeo = trackGeo(new THREE.BoxGeometry(34, 1.2, 32))
  const plinthMesh = new THREE.Mesh(plinthGeo, matGround)
  plinthMesh.position.set(0, -0.6, 0)
  plinthMesh.receiveShadow = true
  baseGroup.add(plinthMesh)

  // Internal Road Network
  // Main East-West Boulevard
  const roadEWGeo = trackGeo(new THREE.BoxGeometry(32, 0.05, 3.8))
  const roadEWMesh = new THREE.Mesh(roadEWGeo, matRoad)
  roadEWMesh.position.set(0, 0.02, 0.8)
  roadEWMesh.receiveShadow = true
  baseGroup.add(roadEWMesh)

  // North-South Access Avenue
  const roadNSGeo = trackGeo(new THREE.BoxGeometry(3.6, 0.05, 30))
  const roadNSMesh = new THREE.Mesh(roadNSGeo, matRoad)
  roadNSMesh.position.set(-2.5, 0.02, 0)
  roadNSMesh.receiveShadow = true
  baseGroup.add(roadNSMesh)

  // Road Dash Markings
  for (let x = -14; x <= 14; x += 3.5) {
    if (Math.abs(x - (-2.5)) < 2.5) continue // Skip intersection
    const dashGeo = trackGeo(new THREE.BoxGeometry(1.6, 0.06, 0.12))
    const dashMesh = new THREE.Mesh(dashGeo, matRoadLine)
    dashMesh.position.set(x, 0.04, 0.8)
    baseGroup.add(dashMesh)
  }

  // Landscaped Curbs & Grass Zones
  const grassAreas = [
    { x: -10, z: 10.5, w: 10, d: 6.5 },
    { x: -9.5, z: -1.8, w: 9, d: 2.2 },
    { x: 5, z: 10.5, w: 12, d: 6.0 },
    { x: 12, z: -1.8, w: 6, d: 2.0 },
  ]

  grassAreas.forEach((area) => {
    const curbGeo = trackGeo(new THREE.BoxGeometry(area.w + 0.3, 0.12, area.d + 0.3))
    const curbMesh = new THREE.Mesh(curbGeo, matConcrete)
    curbMesh.position.set(area.x, 0.06, area.z)
    curbMesh.receiveShadow = true
    baseGroup.add(curbMesh)

    const grassGeo = trackGeo(new THREE.BoxGeometry(area.w, 0.16, area.d))
    const grassMesh = new THREE.Mesh(grassGeo, matGrass)
    grassMesh.position.set(area.x, 0.08, area.z)
    grassMesh.receiveShadow = true
    baseGroup.add(grassMesh)
  })

  // Stylized Low-Poly Architectural Trees
  const treePositions = [
    [-14, 12], [-12, 13], [-7, 12.5], [-5, 12],
    [1, 12.5], [4, 12], [8, 12.5], [13, 12],
    [-14.5, 8], [-14.5, 5], [-14.5, -4], [-14.5, -8],
  ]

  treePositions.forEach(([tx, tz]) => {
    const trunkGeo = trackGeo(new THREE.CylinderGeometry(0.12, 0.16, 0.9, 6))
    const trunkMesh = new THREE.Mesh(trunkGeo, matDarkSteel)
    trunkMesh.position.set(tx, 0.5, tz)
    trunkMesh.castShadow = true
    baseGroup.add(trunkMesh)

    const foliageGeo = trackGeo(new THREE.ConeGeometry(0.8, 1.8, 6))
    const foliageMesh = new THREE.Mesh(foliageGeo, matGrass)
    foliageMesh.position.set(tx, 1.6, tz)
    foliageMesh.castShadow = true
    baseGroup.add(foliageMesh)
  })

  // Perimeter Low Security Wall / Parapet
  const perimWallLGeo = trackGeo(new THREE.BoxGeometry(0.4, 0.6, 31.8))
  const perimWallL = new THREE.Mesh(perimWallLGeo, matPaving)
  perimWallL.position.set(-16.8, 0.3, 0)
  baseGroup.add(perimWallL)

  const perimWallR = new THREE.Mesh(perimWallLGeo, matPaving)
  perimWallR.position.set(16.8, 0.3, 0)
  baseGroup.add(perimWallR)

  rootGroup.add(baseGroup)

  // ── 2. Facility 1: Admin & Operations Center (administration) ───────────
  const adminGroup = new THREE.Group()
  adminGroup.position.set(-9.0, 0, 5.5)

  // Main 3-story concrete podium
  const adminBaseGeo = trackGeo(new THREE.BoxGeometry(8.5, 4.0, 6.5))
  const adminBaseMesh = new THREE.Mesh(adminBaseGeo, matConcrete)
  adminBaseMesh.position.set(0, 2.0, 0)
  registerInteractiveMesh(adminBaseMesh, 'administration', 'Perimeter Frame & Foundation')
  adminGroup.add(adminBaseMesh)

  // Glass Ribbon Strips (Floor 1 & 2)
  const glassStrip1Geo = trackGeo(new THREE.BoxGeometry(8.65, 0.8, 6.65))
  const glassStrip1 = new THREE.Mesh(glassStrip1Geo, matGlass)
  glassStrip1.position.set(0, 1.6, 0)
  registerInteractiveMesh(glassStrip1, 'administration', 'Curtain Wall Level 1')
  adminGroup.add(glassStrip1)

  const glassStrip2Geo = trackGeo(new THREE.BoxGeometry(8.65, 0.8, 6.65))
  const glassStrip2 = new THREE.Mesh(glassStrip2Geo, matGlass)
  glassStrip2.position.set(0, 3.2, 0)
  registerInteractiveMesh(glassStrip2, 'administration', 'Curtain Wall Level 2')
  adminGroup.add(glassStrip2)

  // Upper setback executive tier
  const adminUpperGeo = trackGeo(new THREE.BoxGeometry(5.5, 2.0, 4.8))
  const adminUpperMesh = new THREE.Mesh(adminUpperGeo, matLightConcrete)
  adminUpperMesh.position.set(-0.8, 5.0, 0)
  registerInteractiveMesh(adminUpperMesh, 'administration', 'Executive Setback Atrium')
  adminGroup.add(adminUpperMesh)

  // Penthouse Mechanical Unit
  const hvacGeo = trackGeo(new THREE.BoxGeometry(2.0, 0.8, 2.0))
  const hvacMesh = new THREE.Mesh(hvacGeo, matDarkSteel)
  hvacMesh.position.set(-0.8, 6.4, 0)
  adminGroup.add(hvacMesh)

  // Rooftop Solar Array Frame
  for (let s = -1.2; s <= 1.2; s += 1.2) {
    const solarGeo = trackGeo(new THREE.BoxGeometry(1.6, 0.08, 0.9))
    const solarMesh = new THREE.Mesh(solarGeo, matGlass)
    solarMesh.position.set(2.2, 4.3, s)
    solarMesh.rotation.x = -0.3
    solarMesh.castShadow = true
    adminGroup.add(solarMesh)
  }

  // Front Cantilever Entrance Canopy
  const canopyGeo = trackGeo(new THREE.BoxGeometry(2.8, 0.15, 2.0))
  const canopyMesh = new THREE.Mesh(canopyGeo, matDarkSteel)
  canopyMesh.position.set(0, 1.8, -4.0)
  canopyMesh.castShadow = true
  adminGroup.add(canopyMesh)

  facilitiesMap.set('administration', adminGroup)
  rootGroup.add(adminGroup)

  // ── 3. Facility 2: Production Assembly Hall 1 (production_hall) ───────────
  const prodGroup = new THREE.Group()
  prodGroup.position.set(1.5, 0, -6.5)

  // Main Warehouse Box
  const prodBaseGeo = trackGeo(new THREE.BoxGeometry(14.0, 5.2, 8.5))
  const prodBaseMesh = new THREE.Mesh(prodBaseGeo, matLightConcrete)
  prodBaseMesh.position.set(0, 2.6, 0)
  registerInteractiveMesh(prodBaseMesh, 'production_hall', 'Manufacturing Portal Hall')
  prodGroup.add(prodBaseMesh)

  // Saw-Tooth Roof Ridges with North-Facing Clerestory Glass
  const sawToothCount = 4
  const toothWidth = 14.0 / sawToothCount
  for (let i = 0; i < sawToothCount; i++) {
    const sx = -7.0 + i * toothWidth + toothWidth / 2

    // Slanted Roof Pane
    const slopeGeo = trackGeo(new THREE.BoxGeometry(toothWidth - 0.1, 0.2, 5.0))
    const slopeMesh = new THREE.Mesh(slopeGeo, matDarkSteel)
    slopeMesh.position.set(sx, 6.0, 0.8)
    slopeMesh.rotation.x = 0.38
    slopeMesh.castShadow = true
    prodGroup.add(slopeMesh)

    // Vertical Clerestory Glass
    const clerestoryGeo = trackGeo(new THREE.BoxGeometry(toothWidth - 0.1, 1.4, 0.1))
    const clerestoryMesh = new THREE.Mesh(clerestoryGeo, matGlass)
    clerestoryMesh.position.set(sx, 6.0, -1.8)
    prodGroup.add(clerestoryMesh)
  }

  // Structural Column Exterior Bracing (K-Brace style on front wall)
  for (let cx = -6.0; cx <= 6.0; cx += 4.0) {
    const colGeo = trackGeo(new THREE.BoxGeometry(0.5, 5.4, 0.6))
    const colMesh = new THREE.Mesh(colGeo, matDarkSteel)
    colMesh.position.set(cx, 2.7, 4.35)
    registerInteractiveMesh(colMesh, 'production_hall', `Structural Column at Grid ${cx}`)
    prodGroup.add(colMesh)
  }

  // Heavy Industrial Roll-Up Loading Doors
  for (let dx = -4.0; dx <= 4.0; dx += 4.0) {
    const doorGeo = trackGeo(new THREE.BoxGeometry(2.4, 3.4, 0.15))
    const doorMesh = new THREE.Mesh(doorGeo, matDarkSteel)
    doorMesh.position.set(dx, 1.7, 4.3)
    prodGroup.add(doorMesh)
  }

  // Rooftop Exhaust Cyclones / Dust Separators
  const cycloneGeo = trackGeo(new THREE.CylinderGeometry(0.7, 0.3, 2.2, 12))
  const cyclone1 = new THREE.Mesh(cycloneGeo, matBrightSteel)
  cyclone1.position.set(-4.5, 7.2, 2.2)
  cyclone1.castShadow = true
  prodGroup.add(cyclone1)

  const cyclone2 = new THREE.Mesh(cycloneGeo, matBrightSteel)
  cyclone2.position.set(-2.5, 7.2, 2.2)
  cyclone2.castShadow = true
  prodGroup.add(cyclone2)

  facilitiesMap.set('production_hall', prodGroup)
  rootGroup.add(prodGroup)

  // ── 4. Facility 3: Process Tanks & Silo Battery (storage_tanks) ─────────
  const siloGroup = new THREE.Group()
  siloGroup.position.set(10.5, 0, 5.5)

  // Concrete Retention Berm / Bund Wall
  const bermWallGeo = trackGeo(new THREE.BoxGeometry(9.5, 0.9, 7.5))
  const bermFloorMesh = new THREE.Mesh(bermWallGeo, matConcrete)
  bermFloorMesh.position.set(0, 0.45, 0)
  registerInteractiveMesh(bermFloorMesh, 'storage_tanks', 'Concrete Retention Berm')
  siloGroup.add(bermFloorMesh)

  // Silo 1 (Primary High-Volume Storage Vessel)
  const silo1Geo = trackGeo(new THREE.CylinderGeometry(2.5, 2.5, 6.8, 24))
  const silo1Mesh = new THREE.Mesh(silo1Geo, matBrightSteel)
  silo1Mesh.position.set(-1.6, 4.2, 0.2)
  registerInteractiveMesh(silo1Mesh, 'storage_tanks', 'Silo 01 Primary Vessel')
  siloGroup.add(silo1Mesh)

  // Silo 1 Domed Roof
  const dome1Geo = trackGeo(new THREE.SphereGeometry(2.5, 24, 12, 0, Math.PI * 2, 0, Math.PI * 0.45))
  const dome1Mesh = new THREE.Mesh(dome1Geo, matDarkSteel)
  dome1Mesh.position.set(-1.6, 7.6, 0.2)
  dome1Mesh.castShadow = true
  siloGroup.add(dome1Mesh)

  // Silo 2 (Satellite Tank East)
  const silo2Geo = trackGeo(new THREE.CylinderGeometry(1.6, 1.6, 5.2, 20))
  const silo2Mesh = new THREE.Mesh(silo2Geo, matBrightSteel)
  silo2Mesh.position.set(2.4, 3.4, -1.6)
  registerInteractiveMesh(silo2Mesh, 'storage_tanks', 'Silo 02 Process Vessel')
  siloGroup.add(silo2Mesh)

  const dome2Geo = trackGeo(new THREE.ConeGeometry(1.65, 0.8, 20))
  const dome2Mesh = new THREE.Mesh(dome2Geo, matDarkSteel)
  dome2Mesh.position.set(2.4, 6.4, -1.6)
  siloGroup.add(dome2Mesh)

  // Silo 3 (Satellite Tank South)
  const silo3Mesh = new THREE.Mesh(silo2Geo, matBrightSteel)
  silo3Mesh.position.set(2.4, 3.4, 1.8)
  registerInteractiveMesh(silo3Mesh, 'storage_tanks', 'Silo 03 Chemical Vessel')
  siloGroup.add(silo3Mesh)

  const dome3Mesh = new THREE.Mesh(dome2Geo, matDarkSteel)
  dome3Mesh.position.set(2.4, 6.4, 1.8)
  siloGroup.add(dome3Mesh)

  // Elevated Connecting Catwalk / Walkway Bridge
  const catwalkGeo = trackGeo(new THREE.BoxGeometry(4.2, 0.15, 0.7))
  const catwalkMesh = new THREE.Mesh(catwalkGeo, matDarkSteel)
  catwalkMesh.position.set(0.4, 6.2, 0.1)
  siloGroup.add(catwalkMesh)

  facilitiesMap.set('storage_tanks', siloGroup)
  rootGroup.add(siloGroup)

  // ── 5. Facility 4: Elevated Pipe Bridge (pipe_bridge) ────────────────
  const pipeBridgeGroup = new THREE.Group()
  pipeBridgeGroup.position.set(6.2, 0, 0.8)

  // Space-truss Bridge Structure across the road
  // Pylon Bent 1 (South Side)
  const pylon1Geo = trackGeo(new THREE.BoxGeometry(0.4, 4.6, 2.0))
  const pylon1Mesh = new THREE.Mesh(pylon1Geo, matDarkSteel)
  pylon1Mesh.position.set(-3.5, 2.3, 0)
  registerInteractiveMesh(pylon1Mesh, 'pipe_bridge', 'Pipe Rack Bent 1 Support')
  pipeBridgeGroup.add(pylon1Mesh)

  // Pylon Bent 2 (North Side)
  const pylon2Mesh = new THREE.Mesh(pylon1Geo, matDarkSteel)
  pylon2Mesh.position.set(3.5, 2.3, 0)
  registerInteractiveMesh(pylon2Mesh, 'pipe_bridge', 'Pipe Rack Bent 2 Support')
  pipeBridgeGroup.add(pylon2Mesh)

  // Main Warren Truss Frame Span
  const trussSpanGeo = trackGeo(new THREE.BoxGeometry(7.6, 1.2, 1.8))
  const trussSpanMesh = new THREE.Mesh(trussSpanGeo, matDarkSteel)
  trussSpanMesh.position.set(0, 4.8, 0)
  registerInteractiveMesh(trussSpanMesh, 'pipe_bridge', 'Main Warren Truss Span')
  pipeBridgeGroup.add(trussSpanMesh)

  // Elevated Insulated Pipelines inside the bridge
  const pipeZOffsets = [-0.45, 0, 0.45]
  pipeZOffsets.forEach((pz, idx) => {
    const pipeLGeo = trackGeo(new THREE.CylinderGeometry(0.2, 0.2, 11.0, 16))
    const pipeLMesh = new THREE.Mesh(pipeLGeo, idx === 0 ? matSensorGlow : matBrightSteel)
    pipeLMesh.rotation.z = Math.PI / 2
    pipeLMesh.position.set(0, 4.8, pz)
    pipeLMesh.castShadow = true
    pipeBridgeGroup.add(pipeLMesh)
  })

  facilitiesMap.set('pipe_bridge', pipeBridgeGroup)
  rootGroup.add(pipeBridgeGroup)

  // ── 6. Facility 5: Boiler Plant & Powerhouse (processing_unit) ─────────
  const boilerGroup = new THREE.Group()
  boilerGroup.position.set(11.5, 0, -6.8)

  // Boiler Plant Building
  const boilerBaseGeo = trackGeo(new THREE.BoxGeometry(6.5, 4.8, 6.0))
  const boilerBaseMesh = new THREE.Mesh(boilerBaseGeo, matConcrete)
  boilerBaseMesh.position.set(0, 2.4, 0)
  registerInteractiveMesh(boilerBaseMesh, 'processing_unit', 'Powerhouse Enclosure')
  boilerGroup.add(boilerBaseMesh)

  // Tall Free-Standing Industrial Exhaust Chimney / Stack
  const stackGeo = trackGeo(new THREE.CylinderGeometry(0.45, 0.75, 12.0, 20))
  const stackMesh = new THREE.Mesh(stackGeo, matDarkSteel)
  stackMesh.position.set(1.5, 6.0, -1.8)
  registerInteractiveMesh(stackMesh, 'processing_unit', 'Industrial Exhaust Stack')
  boilerGroup.add(stackMesh)

  // Top Aeronautical Warning Band on Stack
  const stackBandGeo = trackGeo(new THREE.CylinderGeometry(0.48, 0.52, 1.4, 20))
  const stackBandMesh = new THREE.Mesh(stackBandGeo, matSensorGlow)
  stackBandMesh.position.set(1.5, 11.2, -1.8)
  boilerGroup.add(stackBandMesh)

  // Roof Cooling Tower Module
  const coolingBoxGeo = trackGeo(new THREE.BoxGeometry(2.4, 1.2, 2.4))
  const coolingBoxMesh = new THREE.Mesh(coolingBoxGeo, matLightConcrete)
  coolingBoxMesh.position.set(-1.4, 5.4, 0.8)
  boilerGroup.add(coolingBoxMesh)

  const fanCylinderGeo = trackGeo(new THREE.CylinderGeometry(0.9, 0.9, 0.5, 16))
  const fanMesh = new THREE.Mesh(fanCylinderGeo, matDarkSteel)
  fanMesh.position.set(-1.4, 6.2, 0.8)
  boilerGroup.add(fanMesh)

  // Electrical Transformer Substation Yard
  const transYardGeo = trackGeo(new THREE.BoxGeometry(2.5, 1.4, 2.0))
  const transYardMesh = new THREE.Mesh(transYardGeo, matDarkSteel)
  transYardMesh.position.set(-2.2, 0.7, -2.2)
  boilerGroup.add(transYardMesh)

  facilitiesMap.set('processing_unit', boilerGroup)
  rootGroup.add(boilerGroup)

  // ── 7. Facility 6: Southern Logistics Bay (utility_building) ───────────────
  const logGroup = new THREE.Group()
  logGroup.position.set(-6.0, 0, -8.0)

  // Logistics Warehouse Main Body
  const logBaseGeo = trackGeo(new THREE.BoxGeometry(9.0, 4.4, 6.5))
  const logBaseMesh = new THREE.Mesh(logBaseGeo, matLightConcrete)
  logBaseMesh.position.set(0, 2.2, 0)
  registerInteractiveMesh(logBaseMesh, 'utility_building', 'Logistics Terminal Bay')
  logGroup.add(logBaseMesh)

  // Cantilevered Loading Dock Canopy
  const dockCanopyGeo = trackGeo(new THREE.BoxGeometry(8.2, 0.25, 2.8))
  const dockCanopyMesh = new THREE.Mesh(dockCanopyGeo, matDarkSteel)
  dockCanopyMesh.position.set(0, 3.6, 4.2)
  dockCanopyMesh.castShadow = true
  logGroup.add(dockCanopyMesh)

  // Recessed Loading Bay Openings
  for (let bx = -2.6; bx <= 2.6; bx += 2.6) {
    const bayCutoutGeo = trackGeo(new THREE.BoxGeometry(1.8, 2.4, 0.3))
    const bayCutout = new THREE.Mesh(bayCutoutGeo, matDarkSteel)
    bayCutout.position.set(bx, 1.2, 3.2)
    logGroup.add(bayCutout)
  }

  // Parked Semi-Trailer Containers
  const trailerGeo = trackGeo(new THREE.BoxGeometry(1.9, 2.2, 5.0))
  const trailer1 = new THREE.Mesh(trailerGeo, matConcrete)
  trailer1.position.set(-2.6, 1.1, 5.8)
  trailer1.castShadow = true
  logGroup.add(trailer1)

  const trailer2 = new THREE.Mesh(trailerGeo, matConcrete)
  trailer2.position.set(0, 1.1, 5.8)
  trailer2.castShadow = true
  logGroup.add(trailer2)

  facilitiesMap.set('utility_building', logGroup)
  rootGroup.add(logGroup)

  // ── 8. Sensor Markers (Monitoring Mode) ────────────────────────────────────
  CAMPUS_MARKERS.forEach((marker) => {
    const markerGeo = trackGeo(new THREE.SphereGeometry(0.35, 16, 16))
    const markerMesh = new THREE.Mesh(markerGeo, matSensorGlow)
    markerMesh.position.set(marker.worldPos[0], marker.worldPos[1] + 1.2, marker.worldPos[2])
    markerMesh.userData = {
      isSensorMarker: true,
      sensorId: `SENSOR-${marker.id}`,
      assetId: marker.id,
    }
    markerMesh.visible = false
    rootGroup.add(markerMesh)
    sensorMarkersMap.set(marker.id, markerMesh)
    interactiveMeshes.push(markerMesh)

    const stalkGeo = trackGeo(new THREE.CylinderGeometry(0.04, 0.04, 0.8, 8))
    const stalkMesh = new THREE.Mesh(stalkGeo, matDarkSteel)
    stalkMesh.position.set(marker.worldPos[0], marker.worldPos[1] + 0.6, marker.worldPos[2])
    stalkMesh.userData = { isSensorAnchor: true, parentMarkerId: marker.id }
    stalkMesh.visible = false
    rootGroup.add(stalkMesh)
  })

  // ── 9. Defect Markers (Defects Mode) ──────────────────────────────────────
  CAMPUS_MARKERS.forEach((marker) => {
    const defectMarkerGeo = trackGeo(new THREE.TorusGeometry(0.45, 0.1, 12, 24))
    const defectMesh = new THREE.Mesh(defectMarkerGeo, matDefectGlow)
    defectMesh.position.set(marker.worldPos[0], marker.worldPos[1] + 0.5, marker.worldPos[2])
    defectMesh.rotation.x = Math.PI / 2
    defectMesh.userData = {
      isDefectMarker: true,
      defectId: `DEFECT-${marker.id}`,
      assetId: marker.id,
    }
    defectMesh.visible = false
    rootGroup.add(defectMesh)
    defectMarkersMap.set(marker.id, defectMesh)
    interactiveMeshes.push(defectMesh)
  })

  // Cleanup helper
  const cleanup = () => {
    geometriesToDispose.forEach((g) => g.dispose())
    materialsToDispose.forEach((m) => m.dispose())
  }

  return {
    rootGroup,
    facilitiesMap,
    sensorMarkersMap,
    defectMarkersMap,
    interactiveMeshes,
    cleanup,
  }
}

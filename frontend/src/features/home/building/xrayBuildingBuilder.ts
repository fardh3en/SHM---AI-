/**
 * X-Ray 3D Building Procedural Model Builder
 * Full-scene engineering diagnostic digital twin with:
 * - Distinct floor slabs and pale concrete structural moment frame
 * - Rebar reinforcement cages (longitudinal bars + stirrups) inside concrete
 * - Surface crack 3D path geometry with calibrated measurements (184 mm, 0.8 mm)
 * - Internal crack depth cutaway plane (28 mm penetration into 40 mm concrete cover)
 * - Concrete deterioration, delamination & spalling zones
 * - Structural engineering grid axes (X1-X4, A-C) and elevation datum markers
 * - Dynamic mode and layer controllers
 */
import * as THREE from 'three'
import {
  type XRayViewingMode,
  type BuildingFloor,
  FLOOR_ELEVATIONS,
} from './xrayBuildingData'

export interface XRayBuildingBuildResult {
  rootGroup: THREE.Group
  interactiveMeshes: THREE.Mesh[]
  facadeGroup: THREE.Group
  skeletonGroup: THREE.Group
  stairsGroup: THREE.Group
  wireframeGroup: THREE.Group
  highlightGroup: THREE.Group
  rebarGroup: THREE.Group
  crackGroup: THREE.Group
  crackDepthGroup: THREE.Group
  deteriorationGroup: THREE.Group
  engineeringGridGroup: THREE.Group
  interiorLightsGroup: THREE.Group
  setViewingMode: (mode: XRayViewingMode) => void
  highlightColumnC03: (active: boolean) => void
  highlightFloor: (floor: BuildingFloor | null) => void
  toggleSectionCut: (enabled: boolean) => void
  toggleRebar: (enabled: boolean) => void
  toggleDepthCut: (enabled: boolean) => void
  toggleDeterioration: (enabled: boolean) => void
  toggleLayers: (showFacade: boolean) => void
  cleanup: () => void
}

export function buildXRayBuilding(): XRayBuildingBuildResult {
  const rootGroup = new THREE.Group()
  const interactiveMeshes: THREE.Mesh[] = []

  // Structural Sub-Groups
  const foundationGroup = new THREE.Group()
  const skeletonGroup = new THREE.Group()
  const stairsGroup = new THREE.Group()
  const facadeGroup = new THREE.Group()
  const wireframeGroup = new THREE.Group()
  const highlightGroup = new THREE.Group()
  const rebarGroup = new THREE.Group()
  const crackGroup = new THREE.Group()
  const crackDepthGroup = new THREE.Group()
  const deteriorationGroup = new THREE.Group()
  const engineeringGridGroup = new THREE.Group()
  const interiorLightsGroup = new THREE.Group()

  rootGroup.add(foundationGroup)
  rootGroup.add(skeletonGroup)
  rootGroup.add(stairsGroup)
  rootGroup.add(facadeGroup)
  rootGroup.add(wireframeGroup)
  rootGroup.add(highlightGroup)
  rootGroup.add(rebarGroup)
  rootGroup.add(crackGroup)
  rootGroup.add(crackDepthGroup)
  rootGroup.add(deteriorationGroup)
  rootGroup.add(engineeringGridGroup)
  rootGroup.add(interiorLightsGroup)

  // Tracking geometries and materials for complete memory disposal
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

  // Helper to create edge wireframe for a mesh
  const addEdges = (
    mesh: THREE.Mesh,
    color = '#D8D5CC',
    opacity = 0.55,
    targetGroup: THREE.Group = wireframeGroup
  ) => {
    const edgeGeo = trackGeo(new THREE.EdgesGeometry(mesh.geometry, 28))
    const edgeMat = trackMat(
      new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity,
      })
    )
    const line = new THREE.LineSegments(edgeGeo, edgeMat)
    line.position.copy(mesh.position)
    line.rotation.copy(mesh.rotation)
    line.scale.copy(mesh.scale)
    targetGroup.add(line)
    return line
  }

  // Helper to register interactive mesh
  const registerInteractive = (mesh: THREE.Mesh, memberId: string) => {
    mesh.userData = { memberId }
    interactiveMeshes.push(mesh)
  }

  // ── 1. Physically-Based Materials ──────────────────────────────────────────
  const matGroundPlinth = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#22201e',
      roughness: 0.9,
      metalness: 0.1,
    })
  )

  const matRoadAsphalt = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#151514',
      roughness: 0.95,
      metalness: 0.05,
    })
  )

  // Concrete Structural Skeleton (Pale concrete grey #D0CDC4 & warm light grey #A9A69D)
  const matConcreteColumn = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#D0CDC4',
      roughness: 0.72,
      metalness: 0.12,
      transparent: true,
      opacity: 0.92,
    })
  )

  const matConcreteColumnXRay = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#D0CDC4',
      roughness: 0.72,
      metalness: 0.12,
      transparent: true,
      opacity: 0.35, // Allows rebar cage to be seen inside!
      depthWrite: false,
    })
  )

  const matConcreteBeam = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#C5C2B8',
      roughness: 0.75,
      metalness: 0.12,
    })
  )

  const matConcreteSlab = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#A9A69D',
      roughness: 0.78,
      metalness: 0.14,
    })
  )

  const matConcreteCore = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#9E9B93',
      roughness: 0.8,
      metalness: 0.1,
    })
  )

  const matStairTreads = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#B5B2A9',
      roughness: 0.75,
      metalness: 0.15,
    })
  )

  // Exterior Facade & Curtain Glazing
  const matFacadeGlazing = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#DCD8CF',
      roughness: 0.2,
      metalness: 0.45,
      transparent: true,
      opacity: 0.18,
      depthWrite: false,
      side: THREE.DoubleSide,
    })
  )

  const matMullions = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#484540',
      roughness: 0.6,
      metalness: 0.5,
    })
  )

  // Rebar Reinforcement Steel Material
  const matRebarSteel = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#C8A265', // Metallic steel with bronze/copper rebar mill tone
      roughness: 0.3,
      metalness: 0.85,
    })
  )

  const matRebarStirrup = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#A88348',
      roughness: 0.4,
      metalness: 0.8,
    })
  )

  // High-Contrast Diagnostic Defect Materials
  const matCrackPath = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#D8C65A', // Mineral Yellow
      emissive: '#D8C65A',
      emissiveIntensity: 0.8,
      roughness: 0.2,
      metalness: 0.1,
    })
  )

  const matCrackDepthSlice = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#E06A3B', // Terracotta Amber for crack penetration plane
      emissive: '#C2410C',
      emissiveIntensity: 0.6,
      transparent: true,
      opacity: 0.65,
      depthWrite: false,
      side: THREE.DoubleSide,
    })
  )

  const matUltrasonicPlane = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#38BDF8', // Cyan GPR / Ultrasonic acoustic scan slice
      emissive: '#0284C7',
      emissiveIntensity: 0.35,
      transparent: true,
      opacity: 0.25,
      depthWrite: false,
      side: THREE.DoubleSide,
    })
  )

  const matSpallDeterioration = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#8A5D3B', // Rough aggregate rust / carbonation
      roughness: 0.95,
      metalness: 0.05,
    })
  )

  // Column C-03 Glowing Highlight System
  const matColumnHighlightBox = trackMat(
    new THREE.MeshStandardMaterial({
      color: '#D8C65A',
      emissive: '#D8C65A',
      emissiveIntensity: 0.6,
      roughness: 0.3,
      metalness: 0.2,
      transparent: true,
      opacity: 0.38,
      depthWrite: false,
    })
  )

  // ── 2. Building Grid Dimensions ───────────────────────────────────────────
  const floorLevels = [0, 3.6, 7.2, 10.8, 14.4, 18.0]
  const floorHeight = 3.6
  const slabThickness = 0.32
  const colGridX = [-9, -3, 3, 9]
  const colGridZ = [-7, 0, 7]
  const colWidth = 0.7

  // ── 3. Foundation Plinth & Site Ground ─────────────────────────────────────
  const siteGeo = trackGeo(new THREE.BoxGeometry(42, 0.4, 34))
  const siteMesh = new THREE.Mesh(siteGeo, matRoadAsphalt)
  siteMesh.position.set(0, -0.4, 0)
  siteMesh.receiveShadow = true
  foundationGroup.add(siteMesh)

  const plinthGeo = trackGeo(new THREE.BoxGeometry(26, 0.4, 20))
  const plinthMesh = new THREE.Mesh(plinthGeo, matGroundPlinth)
  plinthMesh.position.set(0, -0.1, 0)
  plinthMesh.receiveShadow = true
  foundationGroup.add(plinthMesh)
  addEdges(plinthMesh, '#484540', 0.5, wireframeGroup)

  // ── 4. Ground Floor Entrance Pavilion ─────────────────────────────────────
  const canopyGeo = trackGeo(new THREE.BoxGeometry(6.4, 0.28, 4.2))
  const canopyMesh = new THREE.Mesh(canopyGeo, matConcreteSlab)
  canopyMesh.position.set(-6, 3.8, 9.1)
  registerInteractive(canopyMesh, 'ENTRANCE-PAVILION')
  skeletonGroup.add(canopyMesh)
  addEdges(canopyMesh, '#D8D5CC', 0.65, wireframeGroup)

  const pavGlazingGeo = trackGeo(new THREE.BoxGeometry(6.0, 3.6, 3.8))
  const pavGlazingMesh = new THREE.Mesh(pavGlazingGeo, matFacadeGlazing)
  pavGlazingMesh.position.set(-6, 1.8, 9.0)
  facadeGroup.add(pavGlazingMesh)
  addEdges(pavGlazingMesh, '#D8D5CC', 0.45, wireframeGroup)

  // ── 5. Concrete Structural Columns Grid ───────────────────────────────────
  // Store column meshes so we can toggle Column C-03 transparency in X-Ray
  let colC03Mesh: THREE.Mesh | null = null

  for (let lvl = 0; lvl < 5; lvl++) {
    const yBot = floorLevels[lvl]
    const yCenter = yBot + floorHeight / 2
    const hCol = floorHeight - slabThickness

    colGridX.forEach((cx) => {
      colGridZ.forEach((cz) => {
        if (Math.abs(cx) < 2.5 && cz === 0) return

        const isTargetC03 = cx === 3 && cz === 7 && lvl === 2
        const colGeo = trackGeo(new THREE.BoxGeometry(colWidth, hCol, colWidth))
        const colMesh = new THREE.Mesh(
          colGeo,
          isTargetC03 ? matConcreteColumnXRay : matConcreteColumn
        )
        colMesh.position.set(cx, yCenter, cz)
        colMesh.castShadow = true
        colMesh.receiveShadow = true

        if (isTargetC03) {
          colC03Mesh = colMesh
        }

        const memberId = isTargetC03 ? 'COL-C03' : 'CORE-SHEAR-GF'
        registerInteractive(colMesh, memberId)
        skeletonGroup.add(colMesh)
        addEdges(colMesh, '#D8D5CC', 0.6, wireframeGroup)
      })
    })
  }

  // ── 6. Longitudinal & Transverse Moment Beams ──────────────────────────────
  for (let lvl = 1; lvl <= 5; lvl++) {
    const yBeam = floorLevels[lvl] - 0.28
    const beamH = 0.55
    const beamW = 0.42

    // X-direction girders
    colGridZ.forEach((cz) => {
      for (let i = 0; i < colGridX.length - 1; i++) {
        const x1 = colGridX[i]
        const x2 = colGridX[i + 1]
        const spanX = x2 - x1
        const beamGeo = trackGeo(new THREE.BoxGeometry(spanX - colWidth, beamH, beamW))
        const beamMesh = new THREE.Mesh(beamGeo, matConcreteBeam)
        beamMesh.position.set((x1 + x2) / 2, yBeam, cz)
        registerInteractive(beamMesh, lvl === 2 ? 'BEAM-F2-MOMENT' : 'CORE-SHEAR-GF')
        skeletonGroup.add(beamMesh)
        addEdges(beamMesh, '#D0CDC4', 0.55, wireframeGroup)
      }
    })

    // Z-direction girders
    colGridX.forEach((cx) => {
      for (let j = 0; j < colGridZ.length - 1; j++) {
        const z1 = colGridZ[j]
        const z2 = colGridZ[j + 1]
        const spanZ = z2 - z1
        const beamGeo = trackGeo(new THREE.BoxGeometry(beamW, beamH, spanZ - colWidth))
        const beamMesh = new THREE.Mesh(beamGeo, matConcreteBeam)
        beamMesh.position.set(cx, yBeam, (z1 + z2) / 2)
        registerInteractive(beamMesh, lvl === 2 ? 'BEAM-F2-MOMENT' : 'CORE-SHEAR-GF')
        skeletonGroup.add(beamMesh)
        addEdges(beamMesh, '#D0CDC4', 0.55, wireframeGroup)
      }
    })
  }

  // ── 7. Concrete Floor Slabs ────────────────────────────────────────────────
  for (let lvl = 1; lvl <= 5; lvl++) {
    const ySlab = floorLevels[lvl]
    const isRoof = lvl === 5
    const isLevel2 = lvl === 2

    // Left Wing
    const slabLGeo = trackGeo(new THREE.BoxGeometry(7.8, slabThickness, 14.8))
    const slabL = new THREE.Mesh(slabLGeo, matConcreteSlab)
    slabL.position.set(-5.1, ySlab, 0)
    registerInteractive(slabL, isLevel2 ? 'SLAB-F2' : 'CORE-SHEAR-GF')
    skeletonGroup.add(slabL)
    addEdges(slabL, '#D8D5CC', 0.65, wireframeGroup)

    // Right Wing
    const slabRGeo = trackGeo(new THREE.BoxGeometry(7.8, slabThickness, 14.8))
    const slabR = new THREE.Mesh(slabRGeo, matConcreteSlab)
    slabR.position.set(5.1, ySlab, 0)
    registerInteractive(slabR, isLevel2 ? 'SLAB-F2' : 'CORE-SHEAR-GF')
    skeletonGroup.add(slabR)
    addEdges(slabR, '#D8D5CC', 0.65, wireframeGroup)

    // Central Walkway / Roof
    if (!isRoof) {
      const walkFGeo = trackGeo(new THREE.BoxGeometry(2.4, slabThickness, 4.2))
      const walkF = new THREE.Mesh(walkFGeo, matConcreteSlab)
      walkF.position.set(0, ySlab, 5.3)
      skeletonGroup.add(walkF)
      addEdges(walkF, '#D8D5CC', 0.5, wireframeGroup)

      const walkBGeo = trackGeo(new THREE.BoxGeometry(2.4, slabThickness, 4.2))
      const walkB = new THREE.Mesh(walkBGeo, matConcreteSlab)
      walkB.position.set(0, ySlab, -5.3)
      skeletonGroup.add(walkB)
      addEdges(walkB, '#D8D5CC', 0.5, wireframeGroup)
    } else {
      const roofCentralGeo = trackGeo(new THREE.BoxGeometry(2.4, slabThickness, 14.8))
      const roofCentral = new THREE.Mesh(roofCentralGeo, matConcreteSlab)
      roofCentral.position.set(0, ySlab, 0)
      skeletonGroup.add(roofCentral)
      addEdges(roofCentral, '#D8D5CC', 0.65, wireframeGroup)

      const parapetGeo = trackGeo(new THREE.BoxGeometry(18.2, 1.1, 15.0))
      const parapetMesh = new THREE.Mesh(parapetGeo, matConcreteSlab)
      parapetMesh.position.set(0, 18.55, 0)
      registerInteractive(parapetMesh, 'ROOF-PENTHOUSE')
      skeletonGroup.add(parapetMesh)
      addEdges(parapetMesh, '#D8D5CC', 0.7, wireframeGroup)
    }
  }

  // ── 8. Central Shear Core ──────────────────────────────────────────────────
  const coreH = 19.5
  const coreGeo = trackGeo(new THREE.BoxGeometry(4.2, coreH, 4.6))
  const coreMesh = new THREE.Mesh(coreGeo, matConcreteCore)
  coreMesh.position.set(0, coreH / 2, -1.8)
  registerInteractive(coreMesh, 'CORE-SHEAR-GF')
  skeletonGroup.add(coreMesh)
  addEdges(coreMesh, '#D8D5CC', 0.7, wireframeGroup)

  // ── 9. Dog-Leg Staircases ─────────────────────────────────────────────────
  for (let lvl = 0; lvl < 4; lvl++) {
    const yStart = floorLevels[lvl]
    const midY = yStart + floorHeight / 2
    const flightLength = Math.hypot(floorHeight / 2, 2.6)

    const flight1Geo = trackGeo(new THREE.BoxGeometry(1.2, 0.18, flightLength))
    const flight1 = new THREE.Mesh(flight1Geo, matStairTreads)
    flight1.position.set(-0.65, yStart + floorHeight / 4, 2.5)
    flight1.rotation.x = Math.atan2(floorHeight / 2, 2.6)
    registerInteractive(flight1, 'STAIR-CENTRAL')
    stairsGroup.add(flight1)
    addEdges(flight1, '#E0DDD6', 0.6, wireframeGroup)

    const landingGeo = trackGeo(new THREE.BoxGeometry(2.5, 0.2, 1.4))
    const landing = new THREE.Mesh(landingGeo, matStairTreads)
    landing.position.set(0, midY, 1.2)
    registerInteractive(landing, 'STAIR-CENTRAL')
    stairsGroup.add(landing)
    addEdges(landing, '#E0DDD6', 0.6, wireframeGroup)

    const flight2Geo = trackGeo(new THREE.BoxGeometry(1.2, 0.18, flightLength))
    const flight2 = new THREE.Mesh(flight2Geo, matStairTreads)
    flight2.position.set(0.65, midY + floorHeight / 4, 2.5)
    flight2.rotation.x = -Math.atan2(floorHeight / 2, 2.6)
    registerInteractive(flight2, 'STAIR-CENTRAL')
    stairsGroup.add(flight2)
    addEdges(flight2, '#E0DDD6', 0.6, wireframeGroup)
  }

  // ── 10. Exterior Curtain Glazing ──────────────────────────────────────────
  const totalBldgH = 18.0
  const facadeFrontGeo = trackGeo(new THREE.BoxGeometry(18.0, totalBldgH, 0.15))
  const facadeFront = new THREE.Mesh(facadeFrontGeo, matFacadeGlazing)
  facadeFront.position.set(0, totalBldgH / 2, 7.35)
  facadeGroup.add(facadeFront)
  addEdges(facadeFront, '#E0DDD6', 0.45, wireframeGroup)

  const facadeBackGeo = trackGeo(new THREE.BoxGeometry(18.0, totalBldgH, 0.15))
  const facadeBack = new THREE.Mesh(facadeBackGeo, matFacadeGlazing)
  facadeBack.position.set(0, totalBldgH / 2, -7.35)
  facadeGroup.add(facadeBack)
  addEdges(facadeBack, '#E0DDD6', 0.45, wireframeGroup)

  const facadeSideGeo = trackGeo(new THREE.BoxGeometry(0.15, totalBldgH, 14.7))
  const facadeLeft = new THREE.Mesh(facadeSideGeo, matFacadeGlazing)
  facadeLeft.position.set(-9.05, totalBldgH / 2, 0)
  facadeGroup.add(facadeLeft)
  addEdges(facadeLeft, '#E0DDD6', 0.45, wireframeGroup)

  const facadeRight = new THREE.Mesh(facadeSideGeo, matFacadeGlazing)
  facadeRight.position.set(9.05, totalBldgH / 2, 0)
  facadeGroup.add(facadeRight)
  addEdges(facadeRight, '#E0DDD6', 0.45, wireframeGroup)

  for (let x = -8.5; x <= 8.5; x += 2.0) {
    const mullionGeo = trackGeo(new THREE.BoxGeometry(0.08, totalBldgH, 0.18))
    const mullionF = new THREE.Mesh(mullionGeo, matMullions)
    mullionF.position.set(x, totalBldgH / 2, 7.42)
    facadeGroup.add(mullionF)

    const mullionB = new THREE.Mesh(mullionGeo, matMullions)
    mullionB.position.set(x, totalBldgH / 2, -7.42)
    facadeGroup.add(mullionB)
  }

  // ── 11. REINFORCEMENT LAYER: Rebar Cage Inside Column C-03 & Slabs ─────────
  // Concrete cover: 40mm (0.04m). Column is 0.70m x 0.70m at x = 3, z = 7.
  // Rebar cage footprint is 0.58m x 0.58m centered at (3, 8.8, 7) on Floor 2.
  const rebarH = 3.6 - slabThickness
  const rebarCenterY = 7.2 + slabThickness + rebarH / 2

  // 8 Vertical Longitudinal Rebar Bars (Ø28mm)
  const barGeo = trackGeo(new THREE.CylinderGeometry(0.016, 0.016, rebarH, 12))
  const barOffsets = [
    [-0.25, -0.25],
    [0.0, -0.25],
    [0.25, -0.25],
    [-0.25, 0.25],
    [0.0, 0.25],
    [0.25, 0.25],
    [-0.25, 0.0],
    [0.25, 0.0],
  ]

  barOffsets.forEach(([ox, oz]) => {
    const barMesh = new THREE.Mesh(barGeo, matRebarSteel)
    barMesh.position.set(3 + ox, rebarCenterY, 7 + oz)
    rebarGroup.add(barMesh)
  })

  // Transverse Stirrup Ties (Spaced every 0.35m along column height)
  for (let yOffset = -rebarH / 2 + 0.18; yOffset <= rebarH / 2 - 0.18; yOffset += 0.35) {
    const stirrupGeo = trackGeo(new THREE.BoxGeometry(0.54, 0.014, 0.54))
    const stirrupEdges = trackGeo(new THREE.EdgesGeometry(stirrupGeo))
    const stirrupLine = new THREE.LineSegments(
      stirrupEdges,
      trackMat(new THREE.LineBasicMaterial({ color: '#EAB308', linewidth: 1.5 }))
    )
    stirrupLine.position.set(3, rebarCenterY + yOffset, 7)
    rebarGroup.add(stirrupLine)
  }

  // Post-Tensioned Tendons Grid in Floor 2 Slab
  for (let zTendon = -6.5; zTendon <= 6.5; zTendon += 2.0) {
    const tendonGeo = trackGeo(new THREE.CylinderGeometry(0.01, 0.01, 17.6, 8))
    const tendonMesh = new THREE.Mesh(tendonGeo, matRebarStirrup)
    tendonMesh.rotation.z = Math.PI / 2
    tendonMesh.position.set(0, 7.2, zTendon)
    rebarGroup.add(tendonMesh)
  }

  // ── 12. GENUINE 3D CRACK VISUALIZATION (Surface Path Geometry) ────────────
  // Branching irregular 3D crack on front surface of Column C-03 (z = 7.36)
  const crackPoints = [
    new THREE.Vector3(2.65, 9.35, 7.36),
    new THREE.Vector3(2.78, 9.15, 7.36),
    new THREE.Vector3(2.92, 8.92, 7.36),
    new THREE.Vector3(3.08, 8.68, 7.36),
    new THREE.Vector3(3.24, 8.42, 7.36),
    new THREE.Vector3(3.42, 8.18, 7.36),
  ]

  const crackCurve = new THREE.CatmullRomCurve3(crackPoints)
  const crackGeo = trackGeo(new THREE.TubeGeometry(crackCurve, 32, 0.018, 8, false))
  const crackMesh = new THREE.Mesh(crackGeo, matCrackPath)
  registerInteractive(crackMesh, 'COL-C03')
  crackGroup.add(crackMesh)

  // Secondary Branch (Hairline Fracture propagating upwards-right)
  const branchPoints = [
    new THREE.Vector3(3.08, 8.68, 7.36),
    new THREE.Vector3(3.22, 8.85, 7.36),
    new THREE.Vector3(3.38, 8.98, 7.36),
  ]
  const branchCurve = new THREE.CatmullRomCurve3(branchPoints)
  const branchGeo = trackGeo(new THREE.TubeGeometry(branchCurve, 16, 0.01, 6, false))
  const branchMesh = new THREE.Mesh(branchGeo, matCrackPath)
  crackGroup.add(branchMesh)

  // 3D Measurement Leader Lines for Crack (Length & Width)
  const leaderMat = trackMat(
    new THREE.LineBasicMaterial({
      color: '#D8C65A',
      transparent: true,
      opacity: 0.85,
    })
  )

  // Length dimension offset line
  const lengthDimGeo = trackGeo(
    new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(2.45, 9.35, 7.37),
      new THREE.Vector3(2.45, 8.18, 7.37),
    ])
  )
  crackGroup.add(new THREE.Line(lengthDimGeo, leaderMat))

  // End tick marks
  const tick1Geo = trackGeo(
    new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(2.38, 9.35, 7.37),
      new THREE.Vector3(2.65, 9.35, 7.37),
    ])
  )
  crackGroup.add(new THREE.Line(tick1Geo, leaderMat))

  const tick2Geo = trackGeo(
    new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(2.38, 8.18, 7.37),
      new THREE.Vector3(3.42, 8.18, 7.37),
    ])
  )
  crackGroup.add(new THREE.Line(tick2Geo, leaderMat))

  // ── 13. CRACK DEPTH & CONCRETE COVER PENETRATION VISUALIZATION ────────────
  // Penetrates 28 mm into the 40 mm concrete cover towards the stirrup tie!
  // Crack Depth Plane (Cross-sectional internal fracture sheet)
  const depthPlaneGeo = trackGeo(new THREE.PlaneGeometry(0.85, 1.25))
  const depthPlaneMesh = new THREE.Mesh(depthPlaneGeo, matCrackDepthSlice)
  depthPlaneMesh.position.set(3.05, 8.75, 7.36 - 0.014) // 14mm inward center
  depthPlaneMesh.rotation.y = Math.PI / 4 // 45° internal fracture propagation
  crackDepthGroup.add(depthPlaneMesh)

  // Concrete Cover Depth Dimension Bar (40mm Cover vs 28mm Depth)
  const depthMarkerGeo = trackGeo(
    new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(3.08, 8.68, 7.36),
      new THREE.Vector3(3.08, 8.68, 7.36 - 0.028), // 28 mm deep
    ])
  )
  const depthMarkerLine = new THREE.Line(
    depthMarkerGeo,
    trackMat(new THREE.LineBasicMaterial({ color: '#E06A3B', linewidth: 2 }))
  )
  crackDepthGroup.add(depthMarkerLine)

  // Ultrasonic Pulse Echo / GPR Tomographic Acoustic Plane
  const scanSliceGeo = trackGeo(new THREE.PlaneGeometry(0.9, 3.2))
  const scanSliceMesh = new THREE.Mesh(scanSliceGeo, matUltrasonicPlane)
  scanSliceMesh.position.set(3.0, rebarCenterY, 7.0)
  scanSliceMesh.rotation.y = Math.PI / 2 // Slices through the core of column
  crackDepthGroup.add(scanSliceMesh)

  // ── 14. DETERIORATION & SPALLING VISUALIZATION ─────────────────────────────
  // Spall & delamination zone under Floor 2 slab soffit (x = 3 to 4.5, z = 5.5 to 7.0)
  const spallGeo = trackGeo(new THREE.BoxGeometry(1.4, 0.06, 1.2))
  const spallMesh = new THREE.Mesh(spallGeo, matSpallDeterioration)
  spallMesh.position.set(3.7, 7.17, 6.2)
  registerInteractive(spallMesh, 'SLAB-F2')
  deteriorationGroup.add(spallMesh)
  addEdges(spallMesh, '#C2410C', 0.85, deteriorationGroup)

  // ── 15. ENGINEERING SPATIAL GRID & DATUM SYSTEM ───────────────────────────
  // Ground datum grid lines marking column axes
  const gridLineMat = trackMat(
    new THREE.LineBasicMaterial({
      color: '#414039',
      transparent: true,
      opacity: 0.65,
    })
  )

  // Column Lines along X: -9, -3, 3, 9
  colGridX.forEach((x) => {
    const lineGeo = trackGeo(
      new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(x, 0.01, -12),
        new THREE.Vector3(x, 0.01, 12),
      ])
    )
    engineeringGridGroup.add(new THREE.Line(lineGeo, gridLineMat))
  })

  // Grid Lines along Z: -7, 0, 7
  colGridZ.forEach((z) => {
    const lineGeo = trackGeo(
      new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(-14, 0.01, z),
        new THREE.Vector3(14, 0.01, z),
      ])
    )
    engineeringGridGroup.add(new THREE.Line(lineGeo, gridLineMat))
  })

  // Vertical Elevation Datum Lines
  floorLevels.forEach((elev) => {
    const datumLineGeo = trackGeo(
      new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(10.2, elev, 7.5),
        new THREE.Vector3(11.2, elev, 7.5),
      ])
    )
    engineeringGridGroup.add(new THREE.Line(datumLineGeo, gridLineMat))
  })

  // ── 16. Column C-03 Highlight System ───────────────────────────────────────
  const colC03TotalH = 18.0
  const colC03CasingGeo = trackGeo(new THREE.BoxGeometry(1.6, colC03TotalH, 1.6))
  const colC03Casing = new THREE.Mesh(colC03CasingGeo, matColumnHighlightBox)
  colC03Casing.position.set(3, colC03TotalH / 2, 7)
  registerInteractive(colC03Casing, 'COL-C03')
  highlightGroup.add(colC03Casing)
  addEdges(colC03Casing, '#F6E05E', 0.95, highlightGroup)

  // Target Beacon Ring at Floor 2 (y = 8.7)
  const ringGeo = trackGeo(new THREE.TorusGeometry(0.85, 0.08, 16, 32))
  const ringMesh = new THREE.Mesh(
    ringGeo,
    trackMat(
      new THREE.MeshStandardMaterial({
        color: '#FCE77D',
        emissive: '#D8C65A',
        emissiveIntensity: 0.9,
      })
    )
  )
  ringMesh.position.set(3, 8.7, 7)
  ringMesh.rotation.x = Math.PI / 2
  highlightGroup.add(ringMesh)

  // Localized Point Light
  const colLight = new THREE.PointLight('#D8C65A', 1.8, 16)
  colLight.position.set(3, 8.7, 7)
  highlightGroup.add(colLight)

  // ── 17. Interior Ceiling Lights ───────────────────────────────────────────
  floorLevels.slice(1).forEach((yLevel) => {
    const ceilLight1 = new THREE.PointLight('#FFE4B5', 0.85, 14)
    ceilLight1.position.set(-4, yLevel - 0.5, 2)
    interiorLightsGroup.add(ceilLight1)

    const ceilLight2 = new THREE.PointLight('#FFE4B5', 0.85, 14)
    ceilLight2.position.set(4, yLevel - 0.5, -2)
    interiorLightsGroup.add(ceilLight2)
  })

  // ── 18. Dynamic Viewing Mode Controller ───────────────────────────────────
  const setViewingMode = (mode: XRayViewingMode) => {
    switch (mode) {
      case 'xray': // FULL-SCENE DIAGNOSTIC X-RAY
        facadeGroup.visible = true
        skeletonGroup.visible = true
        stairsGroup.visible = true
        wireframeGroup.visible = true
        highlightGroup.visible = true
        rebarGroup.visible = true
        crackGroup.visible = true
        crackDepthGroup.visible = true
        deteriorationGroup.visible = true
        engineeringGridGroup.visible = true
        interiorLightsGroup.visible = true

        matFacadeGlazing.transparent = true
        matFacadeGlazing.opacity = 0.18
        matFacadeGlazing.depthWrite = false

        if (colC03Mesh) {
          colC03Mesh.material = matConcreteColumnXRay
        }
        break

      case 'exterior':
        facadeGroup.visible = true
        skeletonGroup.visible = true
        stairsGroup.visible = false
        wireframeGroup.visible = false
        highlightGroup.visible = false
        rebarGroup.visible = false
        crackGroup.visible = false
        crackDepthGroup.visible = false
        deteriorationGroup.visible = false
        engineeringGridGroup.visible = false
        interiorLightsGroup.visible = false

        matFacadeGlazing.transparent = false
        matFacadeGlazing.opacity = 0.96
        matFacadeGlazing.depthWrite = true

        if (colC03Mesh) {
          colC03Mesh.material = matConcreteColumn
        }
        break

      case 'structure':
        facadeGroup.visible = false
        skeletonGroup.visible = true
        stairsGroup.visible = true
        wireframeGroup.visible = true
        highlightGroup.visible = true
        rebarGroup.visible = true
        crackGroup.visible = false
        crackDepthGroup.visible = false
        deteriorationGroup.visible = false
        engineeringGridGroup.visible = true
        interiorLightsGroup.visible = true

        if (colC03Mesh) {
          colC03Mesh.material = matConcreteColumn
        }
        break

      case 'defects':
        facadeGroup.visible = true
        skeletonGroup.visible = true
        stairsGroup.visible = true
        wireframeGroup.visible = true
        highlightGroup.visible = true
        rebarGroup.visible = true
        crackGroup.visible = true
        crackDepthGroup.visible = true
        deteriorationGroup.visible = true
        engineeringGridGroup.visible = true
        interiorLightsGroup.visible = true

        matFacadeGlazing.transparent = true
        matFacadeGlazing.opacity = 0.14
        matFacadeGlazing.depthWrite = false

        if (colC03Mesh) {
          colC03Mesh.material = matConcreteColumnXRay
        }
        break
    }
  }

  // Initial State: X-RAY
  setViewingMode('xray')

  // ── Helper Actions ─────────────────────────────────────────────────────────
  const highlightColumnC03 = (active: boolean) => {
    highlightGroup.visible = active
  }

  const highlightFloor = (floor: BuildingFloor | null) => {
    if (!floor) return
    const elev = FLOOR_ELEVATIONS[floor]
    interiorLightsGroup.children.forEach((light) => {
      if (light instanceof THREE.PointLight) {
        const isNear = Math.abs(light.position.y - elev) < 4.0
        light.intensity = isNear ? 1.6 : 0.4
      }
    })
  }

  const toggleSectionCut = (enabled: boolean) => {
    facadeFront.visible = !enabled
    matFacadeGlazing.opacity = enabled ? 0.08 : 0.18
  }

  const toggleRebar = (enabled: boolean) => {
    rebarGroup.visible = enabled
  }

  const toggleDepthCut = (enabled: boolean) => {
    crackDepthGroup.visible = enabled
  }

  const toggleDeterioration = (enabled: boolean) => {
    deteriorationGroup.visible = enabled
  }

  const toggleLayers = (showFacade: boolean) => {
    facadeGroup.visible = showFacade
  }

  // Memory disposal cleanup
  const cleanup = () => {
    geometriesToDispose.forEach((g) => g.dispose())
    materialsToDispose.forEach((m) => m.dispose())
  }

  return {
    rootGroup,
    interactiveMeshes,
    facadeGroup,
    skeletonGroup,
    stairsGroup,
    wireframeGroup,
    highlightGroup,
    rebarGroup,
    crackGroup,
    crackDepthGroup,
    deteriorationGroup,
    engineeringGridGroup,
    interiorLightsGroup,
    setViewingMode,
    highlightColumnC03,
    highlightFloor,
    toggleSectionCut,
    toggleRebar,
    toggleDepthCut,
    toggleDeterioration,
    toggleLayers,
    cleanup,
  }
}

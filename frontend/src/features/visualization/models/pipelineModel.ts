import * as THREE from 'three'
import type { ModelBuildResult, StructuralComponentData } from './types'
import type { Asset } from '../../../api/assets'
import type { Inspection } from '../../../api/inspections'

export function buildPipelineModel(
  asset: Asset,
  inspections: Inspection[]
): ModelBuildResult {
  const group = new THREE.Group()
  const components = new Map<string, StructuralComponentData>()

  const latestInspection = inspections.find((i) => i.defect_count > 0)
  const hasFindings = Boolean(latestInspection)

  const matFindings = new THREE.MeshStandardMaterial({
    color: '#E0564A',
    roughness: 0.35,
    metalness: 0.5,
  })
  const matSupply = new THREE.MeshStandardMaterial({
    color: '#D8C65A', // Mineral yellow for thermal supply
    roughness: 0.4,
    metalness: 0.4,
  })
  const matReturn = new THREE.MeshStandardMaterial({
    color: '#B6BDA8', // Sage for thermal return
    roughness: 0.4,
    metalness: 0.4,
  })
  const matChamber = new THREE.MeshStandardMaterial({
    color: '#3B3A36',
    roughness: 0.8,
    metalness: 0.1,
  })
  const matJacket = new THREE.MeshStandardMaterial({
    color: '#222326',
    roughness: 0.5,
    metalness: 0.2,
  })

  const registerMesh = (
    mesh: THREE.Mesh,
    data: StructuralComponentData,
    material: THREE.Material
  ) => {
    mesh.material = material
    mesh.userData = data
    mesh.castShadow = true
    mesh.receiveShadow = true
    group.add(mesh)
    components.set(data.id, data)
  }

  // ── Concrete Inspection Valve Chamber ────────────────────────────────────
  const chamberGeo = new THREE.BoxGeometry(6, 4.2, 5)
  const chamberMesh = new THREE.Mesh(chamberGeo)
  chamberMesh.position.set(0, 0, 0)
  registerMesh(
    chamberMesh,
    {
      id: 'CHAMBER-VALVE-VAULT',
      name: 'Sector 7 Underground Valve Chamber Vault',
      type: 'valve_manifold',
      material: 'Precast reinforced concrete box culvert',
      status: 'not_assessed',
      designFunction: 'Houses isolation gate valves, bypass lines, and air venting manifold',
      dimensions: '6.0m × 4.2m × 5.0m',
      linkedEvidencePaths: ['/uploads/evidence/district_heating_pipeline_manifold.jpg'],
    },
    matChamber
  )

  // ── Twin Pre-Insulated Pipeline Runs (Supply & Return) ────────────────────
  const pipeRuns = [
    { name: 'Supply Pipe (High Temp 110°C)', z: -1.2, mat: matSupply, type: 'pipe_carrier' as const, id: 'PIPE-SUPPLY-MAIN' },
    { name: 'Return Pipe (Low Temp 65°C)', z: 1.2, mat: matReturn, type: 'pipe_carrier' as const, id: 'PIPE-RETURN-MAIN' },
  ]

  pipeRuns.forEach((run) => {
    // Pipe straight section
    const pipeL = 28
    const pipeGeo = new THREE.CylinderGeometry(0.55, 0.55, pipeL, 24)
    const pipeMesh = new THREE.Mesh(pipeGeo)
    pipeMesh.rotation.z = Math.PI / 2
    pipeMesh.position.set(0, 0, run.z)

    const pipeStatus = hasFindings ? 'assessed_findings' : 'not_assessed'
    const finalMat = pipeStatus === 'assessed_findings' ? matFindings : run.mat

    registerMesh(
      pipeMesh,
      {
        id: run.id,
        name: run.name,
        type: run.type,
        material: asset.material || 'Carbon Steel DIN 2458 / Polyurethane Pre-Insulated',
        status: pipeStatus,
        designFunction: 'Carries pressurized hot district heating water under cyclical thermal expansions',
        dimensions: 'DN 250 (Outer diameter 355mm with jacket) × 28m span',
        defectSummary: hasFindings
          ? `Baseline walkthrough noted potential insulation casing wear and joint distress.`
          : undefined,
        linkedEvidencePaths: [
          '/uploads/evidence/district_heating_preinsulated_pipes.jpg',
          '/uploads/evidence/district_heating_expansion_trench.jpg',
        ],
      },
      finalMat
    )

    // Polyurethane protective jacket collars
    for (let j = -2; j <= 2; j++) {
      if (j === 0) continue // Skip chamber interior
      const jacketGeo = new THREE.CylinderGeometry(0.65, 0.65, 1.2, 20)
      const jacketMesh = new THREE.Mesh(jacketGeo)
      jacketMesh.rotation.z = Math.PI / 2
      jacketMesh.position.set(j * 5.5, 0, run.z)
      registerMesh(
        jacketMesh,
        {
          id: `JACKET-SLEEVE-${run.id}-${j}`,
          name: `Heat-Shrink Joint Casing Collar (${j > 0 ? 'East' : 'West'} +${Math.abs(j)})`,
          type: 'insulation_jacket',
          material: 'Cross-linked high density polyethylene (HDPE)',
          status: 'not_assessed',
          designFunction: 'Watertight moisture barrier sealing weld joint insulation',
          dimensions: 'Diameter 450mm × Length 1.2m',
        },
        matJacket
      )
    }
  })

  return {
    group,
    components,
    modelType: 'Pre-Insulated District Heating Pipeline & Valve Vault',
    isIllustrative: true,
  }
}

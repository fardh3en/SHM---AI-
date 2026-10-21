import type { Asset } from '../../../api/assets'
import type { Inspection } from '../../../api/inspections'
import type { ModelBuildResult } from './types'
import { buildBridgeModel } from './bridgeModel'
import { buildTunnelModel } from './tunnelModel'
import { buildBuildingModel } from './buildingModel'
import { buildPipelineModel } from './pipelineModel'
import { buildRoadModel } from './roadModel'
import { buildDamModel } from './damModel'

/**
 * Creates a representative parametric 3D structural model based on the asset's structural category.
 * Accurately associates verified inspection findings with specific structural components where supported.
 */
export function buildStructuralModel(
  asset: Asset,
  inspections: Inspection[] = []
): ModelBuildResult {
  const assetType = asset.asset_type
  const nameLower = asset.name.toLowerCase()

  // 1. Direct asset category matching
  switch (assetType) {
    case 'bridge':
      return buildBridgeModel(asset, inspections)

    case 'tunnel':
      return buildTunnelModel(asset, inspections)

    case 'building':
      return buildBuildingModel(asset, inspections)

    case 'pipeline':
      return buildPipelineModel(asset, inspections)

    case 'road':
      return buildRoadModel(asset, inspections)

    case 'dam':
      return buildDamModel(asset, inspections)

    case 'other':
    default:
      // 2. Keyword fallback for unclassified assets
      if (nameLower.includes('flyover') || nameLower.includes('overpass') || nameLower.includes('highway') || nameLower.includes('road')) {
        return buildRoadModel(asset, inspections)
      }
      if (nameLower.includes('reservoir') || nameLower.includes('dam') || nameLower.includes('weir') || nameLower.includes('inlet') || nameLower.includes('sluice')) {
        return buildDamModel(asset, inspections)
      }
      if (nameLower.includes('tunnel') || nameLower.includes('tube') || nameLower.includes('subway')) {
        return buildTunnelModel(asset, inspections)
      }
      if (nameLower.includes('building') || nameLower.includes('garage') || nameLower.includes('deck') || nameLower.includes('structure')) {
        return buildBuildingModel(asset, inspections)
      }
      if (nameLower.includes('pipeline') || nameLower.includes('pipe') || nameLower.includes('heating')) {
        return buildPipelineModel(asset, inspections)
      }
      return buildBridgeModel(asset, inspections)
  }
}

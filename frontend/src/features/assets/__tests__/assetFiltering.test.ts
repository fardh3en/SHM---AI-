import { describe, it, expect } from 'vitest'
import { isTestFixture, hasArchivedEvidence } from '../AssetListPage'
import type { Asset } from '../../../api/assets'

describe('Asset Filtering & Clutter Cleanup', () => {
  it('correctly flags automated test fixtures and synthetic test assets', () => {
    expect(isTestFixture({ name: 'End-to-End Test Bridge', description: null })).toBe(true)
    expect(isTestFixture({ name: 'Upload Pier Asset', description: null })).toBe(true)
    expect(isTestFixture({ name: 'Ordering Test Asset', description: null })).toBe(true)
    expect(isTestFixture({ name: 'Test StaticPool', description: null })).toBe(true)
    expect(isTestFixture({ name: 'Wall E2E Test', description: null })).toBe(true)
    expect(isTestFixture({ name: 'test_asset_vite', description: null })).toBe(true)
    expect(isTestFixture({ name: 'Fault Test Bridge', description: null })).toBe(true)
    expect(isTestFixture({ name: 'Pier 12', description: 'Automated test fixture' })).toBe(true)
  })

  it('preserves genuine civil engineering structures and user-created assets', () => {
    expect(isTestFixture({ name: 'Golden Gate Bridge North Pier', description: 'Suspension bridge main pier' })).toBe(false)
    expect(isTestFixture({ name: 'Lincoln Tunnel South Tube', description: 'Underwater vehicular tunnel' })).toBe(false)
    expect(isTestFixture({ name: 'HQ Parking Structure Deck C', description: 'Multistorey precast concrete parking garage' })).toBe(false)
    expect(isTestFixture({ name: 'M25 Junction 14 Flyover', description: 'Post-tensioned concrete box girder' })).toBe(false)
    expect(isTestFixture({ name: 'Brixton Reservoir Inlet Structure', description: 'Potable water containment facility' })).toBe(false)
    expect(isTestFixture({ name: 'District Heating Main — Sector 7', description: 'Pre-insulated municipal steam network' })).toBe(false)
    expect(isTestFixture({ name: 'Brooklyn Bridge Arch', description: 'Historic masonry suspension bridge' })).toBe(false)
    expect(isTestFixture({ name: 'Pier C-2', description: 'Highway overpass column' })).toBe(false)
  })

  it('determines archived evidence presence accurately without deceptive tags', () => {
    const unassessedAsset: Asset = {
      id: 'a1',
      name: 'Unassessed Overpass',
      asset_type: 'bridge',
      status: 'active',
      location: 'Route 10',
      description: 'Standard concrete bridge without photos',
      construction_year: 2000,
      material: 'Concrete',
      design_life_years: 50,
      latest_health_score: null,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    }
    expect(hasArchivedEvidence(unassessedAsset)).toBe(false)

    const assessedAsset: Asset = {
      ...unassessedAsset,
      latest_health_score: 82.5,
    }
    expect(hasArchivedEvidence(assessedAsset)).toBe(true)

    const photoAsset: Asset = {
      ...unassessedAsset,
      description: 'Has visual photographic evidence attached',
    }
    expect(hasArchivedEvidence(photoAsset)).toBe(true)
  })
})

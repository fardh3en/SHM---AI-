import { describe, it, expect } from 'vitest'
import vercelConfig from '../../vercel.json'

describe('Vercel SPA Routing Configuration (frontend/vercel.json)', () => {
  it('vercel.json is valid and defines rewrites array', () => {
    expect(vercelConfig).toBeDefined()
    expect(Array.isArray(vercelConfig.rewrites)).toBe(true)
    expect(vercelConfig.rewrites.length).toBeGreaterThan(0)
  })

  it('defines an SPA fallback rewrite targeting /index.html', () => {
    const fallbackRewrite = vercelConfig.rewrites.find(
      (r: { destination: string }) => r.destination === '/index.html'
    )
    expect(fallbackRewrite).toBeDefined()
    expect(fallbackRewrite?.source).toBeDefined()
  })

  it('rewrites all primary and nested client-side routes to /index.html', () => {
    const fallbackRewrite = vercelConfig.rewrites.find(
      (r: { destination: string }) => r.destination === '/index.html'
    )
    const regex = new RegExp(`^${fallbackRewrite!.source}$`)

    const clientRoutes = [
      '/',
      '/dashboard',
      '/assets',
      '/assets/',
      '/assets/bridge-pier-04',
      '/assets/123',
      '/inspections',
      '/inspections/',
      '/inspections/new',
      '/structural-health',
      '/vision',
      '/vision/',
      '/reports',
      '/reports/',
      // Future routes
      '/settings',
      '/analytics/q3-summary',
    ]

    for (const route of clientRoutes) {
      expect(regex.test(route), `Expected route '${route}' to match rewrite fallback`).toBe(true)
    }
  })

  it('strictly excludes API and upload paths from being rewritten to /index.html', () => {
    const fallbackRewrite = vercelConfig.rewrites.find(
      (r: { destination: string }) => r.destination === '/index.html'
    )
    const regex = new RegExp(`^${fallbackRewrite!.source}$`)

    const protectedPaths = [
      '/api',
      '/api/',
      '/api/v1',
      '/api/v1/',
      '/api/v1/system/health',
      '/api/v1/system/info',
      '/api/v1/assets',
      '/api/v1/assets/',
      '/api/v1/inspections',
      '/api/v1/inspections/insp-123/run',
      '/api/v1/evidence',
      '/uploads',
      '/uploads/',
      '/uploads/evidence/0318fe1ead09_crack_image_sg.jpeg',
      '/uploads/temp.png',
    ]

    for (const p of protectedPaths) {
      expect(regex.test(p), `Expected protected path '${p}' NOT to match rewrite fallback`).toBe(false)
    }
  })
})


import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiGet, apiPost, apiUpload, ApiError } from '../client'

describe('API Client Timeout and Failure Handling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('apiGet returns json data on successful 200 response', async () => {
    const mockData = { id: 'insp-123', status: 'completed' }
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    })

    const result = await apiGet('/api/v1/inspections/insp-123')
    expect(result).toEqual(mockData)
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('apiPost throws ApiError with descriptive message on HTTP error response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'Evidence image missing' }),
    })

    await expect(apiPost('/api/v1/inspections/123/run', {})).rejects.toThrow(ApiError)
    await expect(apiPost('/api/v1/inspections/123/run', {})).rejects.toThrow('Evidence image missing')
  })

  it('apiFetch throws ApiError(408, ...) when request times out or is aborted', async () => {
    // Simulate abort error
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      const error = new Error('The user aborted a request.')
      error.name = 'AbortError'
      // Trigger abort on signal if controller exists
      if (init?.signal) {
        init.signal.abort?.()
      }
      return Promise.reject(error)
    })

    await expect(apiGet('/api/v1/inspections/stuck/run')).rejects.toThrow(ApiError)
    try {
      await apiGet('/api/v1/inspections/stuck/run')
    } catch (err) {
      const apiErr = err as ApiError
      expect(apiErr.errorCode).toBe('TIMEOUT_ERROR')
      expect(apiErr.status).toBe(408)
      expect(apiErr.message).toContain('Request timed out')
    }
  })

  it('apiUpload throws ApiError(408, ...) when file upload times out or aborts', async () => {
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      const error = new Error('The operation was aborted.')
      error.name = 'AbortError'
      if (init?.signal) {
        init.signal.abort?.()
      }
      return Promise.reject(error)
    })

    const formData = new FormData()
    formData.append('file', new Blob(['test']), 'test.jpg')

    await expect(apiUpload('/api/v1/evidence', formData)).rejects.toThrow(ApiError)
    try {
      await apiUpload('/api/v1/evidence', formData)
    } catch (err) {
      const apiErr = err as ApiError
      expect(apiErr.errorCode).toBe('TIMEOUT_ERROR')
      expect(apiErr.status).toBe(408)
      expect(apiErr.message).toContain('Evidence upload timed out')
    }
  })
})

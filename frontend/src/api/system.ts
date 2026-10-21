/**
 * System API — /api/v1/system/*
 * Provides health check and platform info endpoints.
 */
import { apiGet } from './client'

export interface SystemHealth {
  status: string
  timestamp: string
  service: string
  version: string
  environment: string
}

export interface SystemInfo {
  app_name: string
  version: string
  python_version: string
  platform: string
  platform_version: string
  environment: string
  debug: boolean
  api_prefix: string
  default_model: string
  inference_device: string
}

export const systemApi = {
  health: () => apiGet<SystemHealth>('/api/v1/system/health'),
  info:   () => apiGet<SystemInfo>('/api/v1/system/info'),
}

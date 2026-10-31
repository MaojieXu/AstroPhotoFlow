import type { ScienceReference } from '../../data'
import { ApiClientError } from '../../../core/client'
import type { FetchApi } from '../../../core/client'

export interface SirilPreviewRequest {
  reference: ScienceReference
  member_index: number
  consumer_id: string
  generation: number
  linked: boolean
  shadowsclip: number
  targetbg: number
  preview_max_edge?: 512 | 1024 | 2048 | null
  display_balance?: 'auto' | 'preserve' | null
}

export function createSirilPreviewClient(fetchApi: FetchApi) {
  const base = '/astrophotoflow/api/v1/software/packages/siril/autostretch-preview'
  return {
    async render(body: SirilPreviewRequest, signal: AbortSignal): Promise<Blob> {
      const response = await fetchApi(base, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body), signal
      })
      if (!response.ok) {
        const error = await response.json() as { error: { message: string; code: string } }
        throw new ApiClientError(error.error.message, 'service', response.status, error.error.code)
      }
      return response.blob()
    },
    async release(consumer: string): Promise<void> {
      await fetchApi(`${base}/${encodeURIComponent(consumer)}`, { method: 'DELETE', keepalive: true })
    }
  }
}

export interface BundlePreviewRequest {
  reference: ScienceReference
  member_index: number
  consumer_id: string
  generation: number
  package_id: string
  operation_id: string
  parameters: Record<string, unknown>
  preview_max_edge?: 512 | 1024 | 2048 | null
  display_balance?: 'auto' | 'preserve' | null
}

export function createBundlePreviewClient(fetchApi: FetchApi) {
  const base = '/astrophotoflow/api/v1/software/preview'
  return {
    async render(body: BundlePreviewRequest, signal: AbortSignal): Promise<Blob> {
      const response = await fetchApi(base, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal })
      if (!response.ok) {
        const error = await response.json() as { error: { message: string; code: string } }
        throw new ApiClientError(error.error.message, 'service', response.status, error.error.code)
      }
      return response.blob()
    },
    async release(consumer: string): Promise<void> {
      await fetchApi(`${base}/${encodeURIComponent(consumer)}`, { method: 'DELETE', keepalive: true })
    }
  }
}

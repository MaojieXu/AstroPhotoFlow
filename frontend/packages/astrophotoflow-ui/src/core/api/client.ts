import { createClient } from '../../generated/api/client'
import { uiT } from '../i18n'
import { ApiClientError, classifyPlatformError } from './errors'

export type FetchApi = (path: string, init?: RequestInit) => Promise<Response>
export type PlatformClient = ReturnType<typeof createClient>

export interface PlatformClientOptions {
  fetchApi: FetchApi
  baseUrl?: string
}

/** Each workspace owns an instance; no mutation of the generated global client. */
export function createPlatformClient(
  options: PlatformClientOptions
): PlatformClient {
  const origin = window.location.origin
  const fetchApi = options.fetchApi
  const client = createClient({
    baseUrl: options.baseUrl ?? new URL('/astrophotoflow', origin).href,
    // Business JSON must be validated even when a server omits Content-Type.
    // Binary operations explicitly select parseAs:'blob' or 'text'.
    parseAs: 'json',
    fetch: async (input, init) => {
      const request =
        input instanceof Request ? input : new Request(input, init)
      request.signal.throwIfAborted()
      const url = new URL(request.url)
      const path = url.origin === origin ? url.pathname + url.search : url.href
      const body = request.body
        ? request.headers.get('Content-Type')?.includes('application/json')
          ? await request.text()
          : await request.blob()
        : undefined
      try {
        return await fetchApi(path, {
          method: request.method,
          headers: request.headers,
          signal: request.signal,
          credentials: request.credentials,
          cache: request.cache,
          keepalive: request.keepalive,
          mode: request.mode,
          redirect: request.redirect,
          referrer: request.referrer,
          referrerPolicy: request.referrerPolicy,
          integrity: request.integrity,
          ...(body !== undefined ? { body } : {})
        })
      } catch (error) {
        if (error instanceof TypeError)
          throw new ApiClientError(
            uiT('apfUi.cannot_connect_to_the_astrophotoflow_service'),
            'network'
          )
        throw error
      }
    }
  })
  client.interceptors.error.use(classifyPlatformError)
  return client
}

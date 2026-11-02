import { createPlatformClient } from './client'
import type { PlatformClient, FetchApi } from './client'
import { ApiClientError } from './errors'
import { uiT } from '../i18n'

/** Follow a server-provided preview URL without duplicating its resource path. */
export async function readPreviewImage(
  client: PlatformClient,
  url: string,
  signal?: AbortSignal
): Promise<Blob> {
  const { data, response } = await client.get<Blob, unknown, true>({
    baseUrl: window.location.origin,
    url,
    signal,
    cache: 'no-store',
    parseAs: 'blob',
    throwOnError: true
  })
  if (
    !response.headers
      .get('Content-Type')
      ?.toLowerCase()
      .startsWith('image/jpeg')
  )
    throw new ApiClientError(
      uiT('apfUi.the_preview_response_type_does_not_match_the_api_contract'),
      'contract',
      response.status
    )
  return data
}

export function createPreviewImageClient(fetchApi:FetchApi){
 const client=createPlatformClient({fetchApi})
 return {getBlob:(path:string,signal?:AbortSignal)=>readPreviewImage(client,path,signal)}
}

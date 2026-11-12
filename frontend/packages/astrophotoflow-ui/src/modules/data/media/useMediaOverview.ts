import { useQuery } from '@tanstack/vue-query'
import { computed, onScopeDispose, shallowRef, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { workspaceQueryKey } from '../../../core/query/keys'
import { createMediaClient } from '../api/media'

export interface MediaOverviewRequest {
  workspaceId: string
  url: string
  viewKey: string
}
export function useMediaOverview(
  request: MaybeRefOrGetter<MediaOverviewRequest | undefined>,
  client = createMediaClient((path, init) => fetch(path, init))
) {
  const identity = computed(() => {
    const current = toValue(request)
    return current
      ? [
          ...workspaceQueryKey(current.workspaceId),
          'media',
          'overview',
          current.viewKey,
          current.url
        ]
      : ['media-overview-idle']
  })
  const query = useQuery({
    queryKey: identity,
    enabled: computed(() =>
      Boolean(toValue(request)?.workspaceId && toValue(request)?.url)
    ),
    queryFn: async ({ signal }) => {
      const current = toValue(request)
      if (!current) throw new Error('Media overview requires a fixed view')
      const scope = JSON.stringify(identity.value)
      return { scope, blob: await client.image(current.url, signal) }
    },
    staleTime: Infinity,
    gcTime: 0,
    retry: false
  })
  const imageUrl = shallowRef('')
  function release() {
    if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
    imageUrl.value = ''
  }
  watch(
    [query.data, identity],
    ([image]) => {
      release()
      if (toValue(request) && image?.scope === JSON.stringify(identity.value))
        imageUrl.value = URL.createObjectURL(image.blob)
    },
    { flush: 'sync' }
  )
  onScopeDispose(release)
  return {
    imageUrl,
    error: query.error,
    loading: query.isFetching,
    retry: () => query.refetch()
  }
}

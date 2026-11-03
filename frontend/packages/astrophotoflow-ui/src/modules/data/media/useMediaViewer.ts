import { useQueries } from '@tanstack/vue-query'
import { computed, onScopeDispose, shallowRef, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { workspaceQueryKey } from '../../../core/query/keys'
import type {
  MediaSelection,
  MediaViewerRequest,
  createMediaClient
} from '../api/media'
import { useMediaView } from './useMediaView'
import type { MediaViewRequest } from './useMediaView'

/** Bounded current/neighbor reads for one fixed viewer request. Rendering stays in the host. */
export function useMediaViewer(
  workspace: MaybeRefOrGetter<string | undefined>,
  request: MaybeRefOrGetter<MediaViewerRequest>,
  client: ReturnType<typeof createMediaClient>
) {
  const scope = computed(() => {
    const workspaceId = toValue(workspace),
      source = toValue(request)
    return workspaceId
      ? { workspaceId, source, id: crypto.randomUUID() }
      : undefined
  })
  const view = shallowRef<{
    index: number
    selection: Partial<MediaSelection>
  }>({ index: toValue(request).index, selection: {} })
  const positions = computed(() => {
    const { index } = view.value,
      total = toValue(request).total
    return [index, index - 1, index + 1].filter(
      (position) => position >= 0 && position < total
    )
  })
  const members = useQueries({
    queries: computed(() =>
      positions.value.map((index) => {
        const current = scope.value
        return {
          queryKey: current
            ? [
                ...workspaceQueryKey(current.workspaceId),
                'media-viewer',
                current.id,
                index,
                'member'
              ]
            : ['viewer-member-idle', index],
          enabled: Boolean(current),
          queryFn: async ({ signal }: { signal: AbortSignal }) => {
            if (!current) throw new Error('Viewer member requires a workspace')
            const member = await current.source.member(index, signal)
            signal.throwIfAborted()
            return { scope: current.id, index, member }
          },
          staleTime: Infinity,
          gcTime: 0,
          retry: false
        }
      })
    )
  })
  const member = computed(() => {
    const result = members.value[0]?.data
    return result?.scope === scope.value?.id &&
      result?.index === view.value.index
      ? result.member
      : undefined
  })
  const thumbnails = useQueries({
    queries: computed(() =>
      positions.value.map((index, position) => {
        const current = scope.value,
          result = members.value[position]?.data
        const selected =
          result?.scope === current?.id && result?.index === index
            ? result.member
            : undefined
        return {
          queryKey: current
            ? [
                ...workspaceQueryKey(current.workspaceId),
                'media-viewer',
                current.id,
                index,
                'thumbnail',
                selected?.basePath ?? null
              ]
            : ['viewer-thumbnail-idle', index],
          enabled: Boolean(current && selected),
          queryFn: async ({ signal }: { signal: AbortSignal }) => {
            if (!current || !selected)
              throw new Error('Viewer thumbnail requires a fixed member')
            const blob = await client.image(
              selected.basePath + '/thumbnail',
              signal
            )
            signal.throwIfAborted()
            return { scope: current.id, index, blob }
          },
          staleTime: Infinity,
          gcTime: 0,
          retry: false
        }
      })
    )
  })
  const urls = shallowRef(new Map<number, { blob: Blob; url: string }>())
  function release() {
    for (const value of urls.value.values()) URL.revokeObjectURL(value.url)
    urls.value = new Map()
  }
  watch(
    () => thumbnails.value.map((query) => query.data),
    (values) => {
      const next = new Map<number, { blob: Blob; url: string }>()
      for (const value of values) {
        if (
          !value ||
          value.scope !== scope.value?.id ||
          !positions.value.includes(value.index)
        )
          continue
        const old = urls.value.get(value.index)
        next.set(
          value.index,
          old && old.blob === value.blob
            ? old
            : { blob: value.blob, url: URL.createObjectURL(value.blob) }
        )
      }
      for (const [index, old] of urls.value)
        if (next.get(index) !== old) URL.revokeObjectURL(old.url)
      urls.value = next
    },
    { flush: 'sync' }
  )
  const media = useMediaView(
    computed(() => {
      const current = scope.value,
        selected = member.value
      return current && selected
        ? {
            workspaceId: current.workspaceId,
            basePath: selected.basePath,
            selection: { ...selected.selection, ...view.value.selection }
          }
        : undefined
    }),
    client
  )
  const nextRequest = shallowRef<MediaViewRequest>()
  const nextMedia = useMediaView(nextRequest, client)
  let nextOverview: AbortController | undefined
  watch(view, () => {
    nextRequest.value = undefined
    nextOverview?.abort()
    nextOverview = undefined
  }, { flush: 'sync' })
  watch([media.state, () => members.value.map(value => value.data)], () => {
    const current = scope.value
    if (!current || media.state.value?.status !== 'available' || media.state.value.kind !== 'image') {
      nextRequest.value = undefined
      nextOverview?.abort()
      nextOverview = undefined
      return
    }
    const next = members.value.find(value => value.data?.index === view.value.index + 1)?.data
    const target = next?.member
    if (!target || next.scope !== current.id) {
      nextRequest.value = undefined
      return
    }
    if (nextRequest.value?.basePath === target.basePath && nextRequest.value.workspaceId === current.workspaceId) return
    nextRequest.value = { workspaceId: current.workspaceId, basePath: target.basePath,
      selection: { ...target.selection, ...view.value.selection, prefetch: true } }
  })
  watch(nextMedia.state, value => {
    nextOverview?.abort()
    nextOverview = undefined
    if (value?.status !== 'available' || !value.overview_url) return
    const controller = nextOverview = new AbortController()
    void client.image(value.overview_url, controller.signal).catch(() => undefined)
  })
  watch(
    scope,
    () => {
      release()
      nextRequest.value = undefined
      nextOverview?.abort()
      view.value = { index: toValue(request).index, selection: {} }
    },
    { flush: 'sync' }
  )
  onScopeDispose(() => { release(); nextOverview?.abort() })
  function open(index: number, selection: Partial<MediaSelection> = {}) {
    if (index < 0 || index >= toValue(request).total) return
    view.value = { index, selection }
  }
  return {
    open,
    member,
    state: media.state,
    index: computed(() => view.value.index),
    selection: computed(() => view.value.selection),
    scope: computed(() => scope.value?.id),
    thumbnail: computed(() => urls.value.get(view.value.index)?.url ?? ''),
    loading: computed(
      () =>
        Boolean(scope.value) &&
        (members.value[0]?.isPending || media.loading.value)
    ),
    error: computed(() => members.value[0]?.error ?? media.error.value)
  }
}

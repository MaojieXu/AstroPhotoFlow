import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, onScopeDispose, shallowRef, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { ApiClientError } from '../../../core/api/errors'
import { workspaceQueryKey } from '../../../core/query/keys'
import { createMediaClient, mediaSelectionSchema } from '../api/media'
import type { MediaSelection, MediaState } from '../api/media'

export interface MediaViewRequest {
  workspaceId: string
  basePath: string
  selection?: Partial<MediaSelection>
}
type MediaClient = ReturnType<typeof createMediaClient>
type Target = MediaViewRequest & {
  selection: Partial<MediaSelection> & {
    consumer_id: string
    generation: number
  }
  controller: AbortController
}
type Session = { target: Target; stateKey?: string }

/** Owns a display consumer, not a scientific operation or a native queue entry. */
export function useMediaView(
  request: MaybeRefOrGetter<MediaViewRequest | undefined>,
  client: MediaClient = createMediaClient((path, init) => fetch(path, init))
) {
  const cache = useQueryClient()
  const session = shallowRef<Session>()
  let generation = 0
  const recent = new Map<string, MediaState>()
  let recentWorkspace: string | undefined
  function contentKey(target: MediaViewRequest) {
    const { consumer_id: _consumer, generation: _generation, prefetch: _prefetch, ...selection } = mediaSelectionSchema.parse(target.selection ?? {})
    return JSON.stringify([target.workspaceId, target.basePath, selection])
  }
  const key = (target: Target) =>
    [
      ...workspaceQueryKey(target.workspaceId),
      'media',
      target.basePath,
      target.selection.consumer_id,
      target.selection.generation
    ] as const
  const prepare = useMutation({
    mutationFn: (target: Target) =>
      client.prepare(
        target.basePath,
        target.selection,
        target.controller.signal
      ),
    retry: false
  })
  const query = useQuery({
    queryKey: computed(() =>
      session.value ? key(session.value.target) : ['media-view-idle']
    ),
    enabled: computed(() => Boolean(session.value?.stateKey)),
    queryFn: async ({ signal }) => {
      const current = session.value
      if (!current?.stateKey)
        throw new Error('Media status requires a prepared consumer')
      const state = await client.status(
        current.target.basePath,
        current.stateKey,
        AbortSignal.any([signal, current.target.controller.signal])
      )
      if (state.key !== current.stateKey)
        throw new ApiClientError(
          'Media status does not match its prepared view',
          'contract'
        )
      return state
    },
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchInterval: (query) =>
      !query.state.error && query.state.data?.status === 'generating'
        ? 1000
        : false
  })
  const state = computed(() =>
    session.value?.stateKey && query.data.value?.key === session.value.stateKey
      ? query.data.value
      : undefined
  )
  const error = computed(
    () =>
      prepare.error.value ?? query.error.value ?? state.value?.error?.message
  )
  watch(state, value => {
    const target = session.value?.target
    if (!target || value?.status !== 'available') return
    const identity = contentKey(target)
    recent.delete(identity)
    recent.set(identity, value)
    while (recent.size > 4) recent.delete(recent.keys().next().value!)
  })
  const loading = computed(
    () =>
      Boolean(session.value) &&
      !error.value &&
      (prepare.isPending.value || state.value?.status === 'generating')
  )

  function release(current: Session | undefined) {
    if (!current) return
    current.target.controller.abort()
    // Best effort display-interest cleanup; this never means a science process stopped.
    void client
      .release(current.target.basePath, current.target.selection.consumer_id)
      .catch(() => undefined)
  }
  async function begin(value: MediaViewRequest | undefined) {
    release(session.value)
    session.value = undefined
    prepare.reset()
    if (!value?.workspaceId || !value.basePath) return
    if (value.workspaceId !== recentWorkspace) {
      recent.clear()
      recentWorkspace = value.workspaceId
    }
    const selection = value.selection ?? {}
    const target: Target = {
      ...value,
      selection: {
        ...selection,
        ...(selection.slices ? { slices: { ...selection.slices } } : {}),
        ...(selection.display_range
          ? { display_range: [...selection.display_range] }
          : {}),
        consumer_id: crypto.randomUUID(),
        generation: ++generation
      },
      controller: new AbortController()
    }
    const remembered = recent.get(contentKey(target))
    if (remembered) cache.setQueryData(key(target), remembered)
    session.value = { target, stateKey: remembered?.key }
    try {
      const result = await prepare.mutateAsync(target)
      if (session.value?.target !== target || target.controller.signal.aborted)
        return
      cache.setQueryData(key(target), result)
      session.value = { target, stateKey: result.key }
    } catch {
      recent.delete(contentKey(target))
      /* Mutation diagnostics belong to the current display session. No automatic POST replay. */
    }
  }
  watch(
    () => toValue(request),
    (value) => void begin(value),
    { immediate: true, flush: 'sync' }
  )
  onScopeDispose(() => {
    release(session.value)
    session.value = undefined
    recent.clear()
  })
  return { state, loading, error, retry: () => begin(toValue(request)) }
}

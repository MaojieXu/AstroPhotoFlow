import { useMutation } from '@tanstack/vue-query'
import { computed, onScopeDispose, shallowRef, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { bundlePreviewRequestSchema } from '../api/preview'
import type {
  BundlePreviewRequest,
  createBundlePreviewClient
} from '../api/preview'

export interface BundleSampleRequest {
  workspaceId: string
  sourceKey: string
  identity: string
  body: Omit<BundlePreviewRequest, 'consumer_id' | 'generation'>
}
type Target = {
  request: BundleSampleRequest
  key: string
  body: BundlePreviewRequest
  controller: AbortController
  started: boolean
}
/** Optional sample execution is a mutation; debounce is a UI interaction, never a retry. */
export function useBundleSamplePreview(
  request: MaybeRefOrGetter<BundleSampleRequest | undefined>,
  client: ReturnType<typeof createBundlePreviewClient>
) {
  const target = shallowRef<Target>()
  const scheduled = shallowRef<Target>()
  const image = shallowRef('')
  let timer: ReturnType<typeof setTimeout> | undefined
  let generation = 0
  const mutation = useMutation({
    mutationFn: (current: Target) =>
      client.render(current.body, current.controller.signal),
    retry: false
  })
  function clearImage() {
    if (image.value) URL.revokeObjectURL(image.value)
    image.value = ''
  }
  function cancel() {
    clearTimeout(timer)
    timer = undefined
    scheduled.value = undefined
    const current = target.value
    current?.controller.abort()
    if (current?.started)
      void client.release(current.body.consumer_id!).catch(() => undefined)
  }
  async function render(current: Target) {
    if (target.value !== current || current.controller.signal.aborted) return
    scheduled.value = undefined
    current.started = true
    try {
      const blob = await mutation.mutateAsync(current)
      if (target.value !== current || current.controller.signal.aborted) return
      clearImage()
      image.value = URL.createObjectURL(blob)
    } catch {
      /* The mutation owns its diagnostic; an uncertain execution is not replayed. */
    }
  }
  function begin(value: BundleSampleRequest | undefined) {
    const key = JSON.stringify(value)
    if (target.value?.key === key) return
    const previous = target.value
    cancel()
    target.value = undefined
    mutation.reset()
    if (
      !value ||
      previous?.request.workspaceId !== value.workspaceId ||
      previous.request.sourceKey !== value.sourceKey
    )
      clearImage()
    if (!value) return
    const current: Target = {
      request: value,
      key,
      body: bundlePreviewRequestSchema.parse({
        ...value.body,
        consumer_id: crypto.randomUUID(),
        generation: ++generation
      }),
      controller: new AbortController(),
      started: false
    }
    target.value = current
    scheduled.value = current
    timer = setTimeout(() => {
      timer = undefined
      void render(current)
    }, 350)
  }
  watch(() => toValue(request), begin, { immediate: true, flush: 'sync' })
  onScopeDispose(() => {
    cancel()
    target.value = undefined
    clearImage()
  })
  return {
    image,
    error: mutation.error,
    waiting: computed(() => Boolean(scheduled.value)),
    updating: mutation.isPending,
    retry: () => {
      const current = target.value
      if (current) {
        cancel()
        target.value = undefined
        begin(current.request)
      }
    },
    clearImage
  }
}

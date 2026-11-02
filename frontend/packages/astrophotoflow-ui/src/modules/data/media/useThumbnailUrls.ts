import { onScopeDispose, shallowRef } from 'vue'

/** Object URLs belong to this view, rather than to the server-data cache. */
export function useThumbnailUrls<T>(
  getId: (item: T) => string,
  read: (item: T, signal: AbortSignal) => Promise<Blob | undefined>
) {
  const urls = shallowRef<Record<string, string>>({})
  let controller: AbortController | undefined
  const pending = new Map<string, object>()

  function cancel() {
    controller?.abort()
    controller = undefined
    pending.clear()
  }

  function clear() {
    cancel()
    for (const url of Object.values(urls.value)) URL.revokeObjectURL(url)
    urls.value = {}
  }

  async function load(items: readonly T[]) {
    clear()
    const current = new AbortController()
    controller = current
    for (const item of items) {
      if (current.signal.aborted) return
      try {
        await publish(item, current)
      } catch {
        // An unavailable display preview is never replaced with a science input.
        if (current.signal.aborted) return
      }
    }
  }

  async function publish(item: T, current: AbortController) {
    const id = getId(item), token = {}
    pending.set(id, token)
    const blob = await read(item, current.signal)
    publishBlob(id, token, blob, current)
  }

  function publishBlob(id: string, token: object, blob: Blob | undefined, current: AbortController) {
    if (current !== controller || current.signal.aborted || pending.get(id) !== token || !blob) return
    const previous = urls.value[id]
    const url = URL.createObjectURL(blob)
    if (previous) URL.revokeObjectURL(previous)
    urls.value = { ...urls.value, [id]: url }
  }

  // Aliases are distinct visible positions referring to the same immutable content.
  async function refresh(item: T, aliases: readonly T[] = [item]) {
    const current = controller
    if (!current || current.signal.aborted) return
    const slots = aliases.map(alias => {
      const id = getId(alias), token = {}
      pending.set(id, token)
      return { id, token }
    })
    try {
      const blob = await read(item, current.signal)
      for (const slot of slots) publishBlob(slot.id, slot.token, blob, current)
    }
    catch (cause) {
      if (current === controller && !current.signal.aborted) throw cause
    }
  }

  onScopeDispose(clear)
  return { urls, load, refresh, clear, cancel }
}

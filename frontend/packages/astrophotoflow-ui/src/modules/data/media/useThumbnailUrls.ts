import { onScopeDispose, reactive, shallowRef } from 'vue'

/** Object URLs belong to this view, rather than to the server-data cache. */
export function useThumbnailUrls<T>(
  getId: (item: T) => string,
  read: (item: T, signal: AbortSignal) => Promise<Blob | undefined>
) {
  const urls = shallowRef(reactive<Record<string, string>>({}))
  let controller: AbortController | undefined
  const pending = new Map<string, object>()
  let members = new Set<string>()
  let candidates: T[] = []
  let loading: Promise<void> | undefined

  function cancel() {
    controller?.abort()
    controller = undefined
    pending.clear()
    candidates = []
    loading = undefined
    members.clear()
  }

  function clear() {
    cancel()
    for (const url of Object.values(urls.value)) URL.revokeObjectURL(url)
    urls.value = reactive({})
  }

  async function load(items: readonly T[]) {
    const retained = new Set(items.map(getId))
    const unchanged = retained.size === members.size && [...retained].every(id => members.has(id))
    if (unchanged && controller) return loadMissing(items)
    cancel()
    members = retained
    for (const [id, url] of Object.entries(urls.value)) {
      if (!retained.has(id)) {
        URL.revokeObjectURL(url)
        delete urls.value[id]
      }
    }
    const current = new AbortController()
    controller = current
    await loadMissing(items)
  }

  async function loadMissing(items: readonly T[]) {
    const current = controller
    if (!current || current.signal.aborted) return
    const queued = new Set(candidates.map(getId))
    for (const item of items) {
      const id = getId(item)
      if (!urls.value[id] && !pending.has(id) && !queued.has(id)) {
        candidates.push(item)
        queued.add(id)
      }
    }
    if (loading) return loading
    const work = Promise.all(Array.from({ length: 4 }, async () => {
      while (current === controller && !current.signal.aborted) {
        const item = candidates.shift()
        if (!item) return
        try { await publish(item, current) }
        catch { if (current.signal.aborted) return }
      }
    })).then(() => undefined).finally(() => {
      if (loading === work) loading = undefined
    })
    loading = work
    return work
  }

  function prioritize(items: readonly T[]) {
    const preferred = new Set(items.map(getId))
    candidates = [...items.filter(item => !urls.value[getId(item)] && !pending.has(getId(item))),
      ...candidates.filter(item => !preferred.has(getId(item)))]
    void loadMissing([])
  }

  async function publish(item: T, current: AbortController) {
    const id = getId(item), token = {}
    pending.set(id, token)
    try {
      const blob = await read(item, current.signal)
      publishBlob(id, token, blob, current)
    } finally {
      if (pending.get(id) === token) pending.delete(id)
    }
  }

  function publishBlob(id: string, token: object, blob: Blob | undefined, current: AbortController) {
    if (current !== controller || current.signal.aborted || pending.get(id) !== token || !blob) return
    const previous = urls.value[id]
    const url = URL.createObjectURL(blob)
    if (previous) URL.revokeObjectURL(previous)
    urls.value[id] = url
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
    finally {
      for (const slot of slots)
        if (pending.get(slot.id) === slot.token) pending.delete(slot.id)
    }
  }

  onScopeDispose(clear)
  return { urls, load, loadMissing, prioritize, refresh, clear, cancel }
}

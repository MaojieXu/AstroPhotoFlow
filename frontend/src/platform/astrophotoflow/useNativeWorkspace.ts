import { computed, onScopeDispose, ref } from 'vue'
import { useWorkspaceIdentity } from '@astrophotoflow/ui'
import { api } from '@/scripts/api'

const connectionId = ref<string>()
let users = 0
const fetchApi = (path: string, init?: RequestInit) => fetch(path, init)
function reconnecting() {
  connectionId.value = undefined
}
function reconnected() {
  connectionId.value = crypto.randomUUID()
}

/** Shared native transport identity; contains no graph, results or service data. */
export function useNativeWorkspace() {
  if (users++ === 0) {
    reconnected()
    api.addEventListener('reconnecting', reconnecting)
    api.addEventListener('reconnected', reconnected)
  }
  const query = useWorkspaceIdentity(fetchApi, connectionId)
  const ready = computed(
    () =>
      Boolean(connectionId.value) &&
      query.isSuccess.value &&
      !query.isFetching.value
  )
  onScopeDispose(() => {
    if (--users === 0) {
      api.removeEventListener('reconnecting', reconnecting)
      api.removeEventListener('reconnected', reconnected)
      connectionId.value = undefined
    }
  })
  return {
    workspaceId: computed(() =>
      ready.value ? query.data.value?.workspace : undefined
    ),
    ready,
    error: query.error,
    refresh: query.refetch
  }
}

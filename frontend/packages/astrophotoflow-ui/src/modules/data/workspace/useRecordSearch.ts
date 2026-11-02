import { onScopeDispose, ref, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'

/** Debounce typing; explicit navigation/filter changes adopt their search immediately. */
export function useRecordSearch(
  input: MaybeRefOrGetter<string>,
  scope: MaybeRefOrGetter<string>
) {
  const query = ref(toValue(input))
  const pending = ref(false)
  let timer: ReturnType<typeof setTimeout> | undefined
  watch(
    [() => toValue(input), () => toValue(scope)],
    ([value, currentScope], [, previousScope]) => {
      clearTimeout(timer)
      if (currentScope !== previousScope || value === query.value) {
        query.value = value
        pending.value = false
        return
      }
      pending.value = true
      timer = setTimeout(() => {
        query.value = value
        pending.value = false
      }, 250)
    }
  )
  onScopeDispose(() => clearTimeout(timer))
  return { query, pending }
}

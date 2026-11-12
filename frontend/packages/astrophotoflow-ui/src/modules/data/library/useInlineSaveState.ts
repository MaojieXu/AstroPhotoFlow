import { computed, onScopeDispose, ref } from 'vue'

/** Editing UI state only. Accepted mutations are never replayed or cancelled. */
export function useInlineSaveState(viewActive: () => boolean) {
  const savingInline = ref(0)
  const failures = ref<Record<string, string>>({})
  const inlineSaveFailure = computed(
    () => Object.values(failures.value).at(-1) ?? ''
  )
  let settled: Promise<void> = Promise.resolve()
  let settle: (() => void) | undefined
  let disposed = false

  function beginInlineSave() {
    if (savingInline.value === 0)
      settled = new Promise((resolve) => {
        settle = resolve
      })
    savingInline.value++
  }
  function finishInlineSave() {
    if (--savingInline.value === 0) {
      settle?.()
      settle = undefined
    }
  }
  function setInlineSaveFailure(key: string, message: string) {
    failures.value = { ...failures.value, [key]: message }
  }
  function clearInlineSaveFailure(key: string) {
    if (!(key in failures.value)) return
    const next = { ...failures.value }
    delete next[key]
    failures.value = next
  }
  async function waitForInlineSave() {
    while (savingInline.value && !disposed && viewActive()) await settled
    return !disposed && viewActive() && !inlineSaveFailure.value
  }
  onScopeDispose(() => {
    disposed = true
    settle?.()
    settle = undefined
  })
  return {
    savingInline,
    inlineSaveFailure,
    beginInlineSave,
    finishInlineSave,
    setInlineSaveFailure,
    clearInlineSaveFailure,
    waitForInlineSave
  }
}

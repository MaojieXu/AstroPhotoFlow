import { computed, inject } from 'vue'
import type { InjectionKey, Ref } from 'vue'

/** A read-only connection gate; carries no resource data, clients or commands. */
export const queryAvailabilityKey: InjectionKey<Readonly<Ref<boolean>>> =
  Symbol('platform-query-availability')

export function useQueryAvailability(): Readonly<Ref<boolean>> {
  return inject(
    queryAvailabilityKey,
    computed(() => true)
  )
}

import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import type { Plugin } from 'vue'

export function createPlatformQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        networkMode: 'always',
        retry: false,
        staleTime: 5_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false
      },
      mutations: { networkMode: 'always', retry: false }
    }
  })
}

/** One cache per native Vue application; workspace identity belongs in every key. */
export const PlatformQueryPlugin: Plugin = {
  install(app) {
    const queryClient = createPlatformQueryClient()
    app.use(VueQueryPlugin, { queryClient })
    app.onUnmount(() => queryClient.clear())
  }
}

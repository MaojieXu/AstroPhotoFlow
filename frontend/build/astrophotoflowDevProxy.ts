import type { ProxyOptions } from 'vite'

export function createWorkbenchDevProxy(target: string): ProxyOptions {
  const targetOrigin = new URL(target).origin
  return {
    changeOrigin: true,
    configure(proxy) {
      proxy.on('proxyReq', (proxyRequest, request) => {
        const origin = request.headers.origin
        if (origin && URL.canParse(origin) && new URL(origin).host === request.headers.host) {
          proxyRequest.setHeader('Origin', targetOrigin)
        }
      })
      proxy.on('proxyReqWs', (proxyRequest, request) => {
        const origin = request.headers.origin
        if (origin && URL.canParse(origin) && new URL(origin).host === request.headers.host) {
          proxyRequest.setHeader('Origin', targetOrigin)
        }
      })
    }
  }
}

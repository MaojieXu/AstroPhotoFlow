import { createServer as createHttpServer, request } from 'node:http'

import { expect, it, onTestFinished } from 'vitest'
import { createServer } from 'vite'

import { createWorkbenchDevProxy } from './astrophotoflowDevProxy'

it('forwards the local development origin and rejects a foreign origin', async () => {
  const backend = createHttpServer((request, response) => {
    response.statusCode = request.headers.origin === target ? 200 : 403
    response.end('result')
  })
  await new Promise<void>(resolve => backend.listen(0, '127.0.0.1', resolve))
  onTestFinished(() => new Promise<void>((resolve, reject) => backend.close(error => error ? reject(error) : resolve())))
  const address = backend.address()
  expect(address && typeof address !== 'string').toBe(true)
  if (!address || typeof address === 'string') return
  const target = `http://127.0.0.1:${address.port}`
  const vite = await createServer({
    configFile: false,
    optimizeDeps: { noDiscovery: true, include: [] },
    server: { host: '127.0.0.1', port: 0, proxy: {
      '/astrophotoflow': { target, ...createWorkbenchDevProxy(target) }
    } }
  })
  onTestFinished(() => vite.close())
  await vite.listen()
  const frontend = vite.httpServer?.address()
  expect(frontend && typeof frontend !== 'string').toBe(true)
  if (!frontend || typeof frontend === 'string') return
  const origin = `http://127.0.0.1:${frontend.port}`
  function statusThroughProxy(requestOrigin: string): Promise<number> {
    return new Promise((resolve, reject) => {
      const pending = request(origin + '/astrophotoflow/api/v1/health', {
        method: 'POST', headers: { Origin: requestOrigin }
      }, response => {
        response.resume()
        response.on('end', () => resolve(response.statusCode ?? 0))
      })
      pending.on('error', reject)
      pending.end()
    })
  }
  expect(await statusThroughProxy(origin)).toBe(200)
  expect(await statusThroughProxy('https://unrelated.example')).toBe(403)
})

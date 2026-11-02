import { test, expect } from '../../frontend/node_modules/@playwright/test/index.mjs'
import { randomUUID } from 'node:crypto'
import { writeFile } from 'node:fs/promises'
import { z } from '../../frontend/node_modules/zod/index.js'
import { zCanvasPageOut, zCanvasAddResult, zErrorEnvelope, zNodeCapability } from '../../frontend/packages/astrophotoflow-ui/src/generated/api/zod.gen'
import { reportRoot } from './modernization-paths.mjs'

test.skip(process.env.APF_ALLOW_CANVAS_MUTATIONS !== '1', 'Explicit opt-in required for the private canvas')

test('workflow saving uses the native file dialog and native JSON storage', async ({ page, request }) => {
  const health = await request.get('/astrophotoflow/api/v1/health')
  expect((await health.json()).workspace.replaceAll('\\', '/').toLowerCase()).toContain('/.artifacts/workspaces/modernization-current')
  const filename = 'G7-native-save-' + randomUUID()
  let queued = 0
  page.on('request', request => { if (request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/prompt')) queued++ })
  await page.goto('/')
  await page.waitForFunction(() => Boolean(window.app?.graph && window.LiteGraph?.registered_node_types.APF_DATA_REFERENCE))
  const draft = await page.evaluate(async () => {
    const app = window.app
    app.graph.clear()
    const node = window.LiteGraph.createNode('APF_DATA_REFERENCE')
    node.properties.apfAutomaticResult = false
    app.graph.add(node)
    const workflow = await app.loadGraphData(app.graph.serialize(), true, true, null, { skipAssetScans: true })
    app.canvas.canvas.focus()
    return { isPersisted: workflow?.isPersisted }
  })
  expect(draft.isPersisted).toBe(false)
  const saved = page.waitForResponse(response => response.request().method() === 'POST' && decodeURIComponent(new URL(response.url()).pathname).endsWith(`/workflows/${filename}.json`))
  await page.keyboard.press('Control+s')
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  const input = dialog.getByRole('textbox')
  await input.fill(filename)
  await input.press('Enter')
  const response = await saved
  expect(response.ok()).toBe(true)
  const file = await request.get(response.url())
  expect(file.ok()).toBe(true)
  const graph = await file.json()
  expect(graph.nodes).toHaveLength(1)
  expect(graph.nodes[0].type).toBe('APF_DATA_REFERENCE')
  expect(queued).toBe(0)
  await writeFile(new URL('native-workflow-save.json', reportRoot), JSON.stringify({ draft, native_url: response.url(), graph, queued }, null, 2))
})

test('canvas mutation uses native undo and stops on changed content, switched graph and closed page', async ({ page, request }) => {
  test.setTimeout(120_000)
  const health = await request.get('/astrophotoflow/api/v1/health')
  expect(health.ok()).toBe(true)
  expect((await health.json()).workspace.replaceAll('\\', '/').toLowerCase()).toContain('/.artifacts/workspaces/modernization-current')
  const name = 'G7 Canvas ' + randomUUID()
  let queued = 0
  page.on('request', request => { if (request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/prompt')) queued++ })
  await page.goto('/')
  await page.waitForFunction(() => Boolean(window.app?.graph && window.app.api.socket?.readyState === WebSocket.OPEN))
  async function newGraph(title: string) {
    await page.evaluate(async title => {
      const app = window.app
      app.graph.clear()
      await app.loadGraphData(app.graph.serialize(), true, true, title + '.json', { skipAssetScans: true })
    }, title)
  }
  async function target(title: string) {
    let observed: z.infer<typeof zCanvasPageOut> | undefined
    await expect.poll(async () => {
      const response = await request.get('/astrophotoflow/api/v1/canvas/pages')
      expect(response.ok()).toBe(true)
      observed = z.array(zCanvasPageOut).parse(await response.json()).find(item => item.title.includes(title))
      return Boolean(observed)
    }).toBe(true)
    const { title: _, ...value } = observed!
    return value
  }
  const nodes = await request.get('/astrophotoflow/api/v1/nodes?query=autostretch')
  const capability = z.array(zNodeCapability).parse(await nodes.json()).find(node => node.operation?.operation_id === 'autostretch')!
  await newGraph(name)
  const initial = await target(name)
  const createdResponse = await request.post('/astrophotoflow/api/v1/canvas/graph', {
    data: { ...initial, operation_id: randomUUID(), edit: { action: 'add_node', definition_id: capability.node.definition.definition_id } },
  })
  expect(createdResponse.ok()).toBe(true)
  const created = zCanvasAddResult.parse(await createdResponse.json())
  expect(created.applied).toBe(true)
  const id = String(created.node_id)
  await expect.poll(() => page.evaluate(id => window.app.graph.nodes.some(node => String(node.id) === id), id)).toBe(true)
  await page.evaluate(() => window.app.canvas.canvas.focus())
  await page.keyboard.press('Control+z')
  await expect.poll(() => page.evaluate(id => window.app.graph.nodes.some(node => String(node.id) === id), id)).toBe(false)
  await page.keyboard.press('Control+Shift+z')
  await expect.poll(() => page.evaluate(id => window.app.graph.nodes.some(node => String(node.id) === id), id)).toBe(true)
  const beforeUnknown = await target(name)
  await page.evaluate(() => {
    const api = window.app.api
    const original = api.sendCanvasEvent.bind(api)
    let held: Parameters<typeof api.sendCanvasEvent>[0] | undefined
    api.sendCanvasEvent = event => {
      if (event.action === 'result') { held = event; return true }
      return original(event)
    }
    Reflect.set(window, Symbol.for('g7-release-canvas-receipt'), () => {
      api.sendCanvasEvent = original
      if (!held) throw new Error('No native receipt was held')
      original(held)
    })
  })
  const unknownId = randomUUID()
  const unknownResponse = await request.post('/astrophotoflow/api/v1/canvas/graph', {
    data: { ...beforeUnknown, operation_id: unknownId, edit: { action: 'set_parameter', node_id: id, name: 'linked', value: true } },
  })
  const unknown = zCanvasAddResult.parse(await unknownResponse.json())
  expect(unknown.applied).toBeNull()
  expect(unknown.error?.code).toBe('CANVAS_RESULT_UNKNOWN')
  const awaitingReceipt = await request.get(`/astrophotoflow/api/v1/canvas/requests/${unknownId}`)
  expect(zCanvasAddResult.parse(await awaitingReceipt.json()).applied).toBeNull()
  await page.evaluate(() => {
    const release = Reflect.get(window, Symbol.for('g7-release-canvas-receipt')) as () => void
    release()
    Reflect.deleteProperty(window, Symbol.for('g7-release-canvas-receipt'))
  })
  let resolvedUnknown = unknown
  await expect.poll(async () => {
    const receipt = await request.get(`/astrophotoflow/api/v1/canvas/requests/${unknownId}`)
    resolvedUnknown = zCanvasAddResult.parse(await receipt.json())
    return resolvedUnknown.applied
  }).toBe(true)
  expect(resolvedUnknown.operation_id).toBe(unknownId)
  const beforeEdit = await target(name)
  await page.evaluate(id => {
    const graph = window.app.graph
    graph.beforeChange()
    graph.getNodeById(id).title = 'User changed content'
    graph.afterChange()
  }, id)
  const staleId = randomUUID()
  const staleResponse = await request.post('/astrophotoflow/api/v1/canvas/graph', {
    data: { ...beforeEdit, operation_id: staleId, edit: { action: 'delete_node', node_id: id } },
  })
  const stale = staleResponse.ok() ? zCanvasAddResult.parse(await staleResponse.json()) : zErrorEnvelope.parse(await staleResponse.json())
  if ('applied' in stale) expect(stale.applied).toBe(false)
  else expect(staleResponse.status()).toBe(409)
  expect(stale.error?.code).toBe('CANVAS_TARGET_CHANGED')
  expect(await page.evaluate(id => Boolean(window.app.graph.getNodeById(id)), id)).toBe(true)
  const receiptResponse = await request.get(`/astrophotoflow/api/v1/canvas/requests/${staleId}`)
  if ('applied' in stale) expect(zCanvasAddResult.parse(await receiptResponse.json()).applied).toBe(false)
  else expect(receiptResponse.status()).toBe(404)
  const previous = await target(name)
  await newGraph(name + ' switched')
  const last = await target(name + ' switched')
  const switchedResponse = await request.post('/astrophotoflow/api/v1/canvas/graph', {
    data: { ...previous, operation_id: randomUUID(), edit: { action: 'delete_node', node_id: id } },
  })
  expect(switchedResponse.status()).toBe(409)
  const switched = zErrorEnvelope.parse(await switchedResponse.json())
  expect(switched.error.code).toBe('CANVAS_TARGET_CHANGED')
  expect(await page.evaluate(() => window.app.graph.nodes.length)).toBe(0)
  await page.close()
  await expect.poll(async () => {
    const response = await request.get('/astrophotoflow/api/v1/canvas/pages')
    return z.array(zCanvasPageOut).parse(await response.json()).some(item => item.page_id === last.page_id)
  }).toBe(false)
  const closedId = randomUUID()
  const closedResponse = await request.post('/astrophotoflow/api/v1/canvas/graph', {
    data: { ...last, operation_id: closedId, edit: { action: 'add_node', definition_id: capability.node.definition.definition_id } },
  })
  expect(closedResponse.status()).toBe(409)
  const closed = zErrorEnvelope.parse(await closedResponse.json())
  expect(closed.error.code).toBe('CANVAS_OFFLINE')
  const closedReceipt = await request.get(`/astrophotoflow/api/v1/canvas/requests/${closedId}`)
  // Preflight rejection never accepted a native operation: querying that ID
  // reports not found rather than manufacturing an applied/unknown receipt.
  expect(closedReceipt.status()).toBe(404)
  expect(queued).toBe(0)
  await writeFile(new URL('native-canvas-guards.json', reportRoot), JSON.stringify({ initial, created, unknown, resolvedUnknown, stale, switched, closed, queued }, null, 2))
})

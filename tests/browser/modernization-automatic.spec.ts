import { test, expect } from '../../frontend/node_modules/@playwright/test/index.mjs'
import { writeFile } from 'node:fs/promises'
import { z } from '../../frontend/node_modules/zod/index.js'
import { zAssetPage, zNodeCapability, zSoftwareCallResult } from '../../frontend/packages/astrophotoflow-ui/src/generated/api/zod.gen'
import { reportRoot } from './modernization-paths.mjs'

test.skip(process.env.APF_ALLOW_NATIVE_SCIENCE !== '1', 'Explicit private real scientific queue opt-in')

test('automatic full result uses native queue and ignores a real old result on another graph', async ({ page, request }) => {
  test.setTimeout(120_000)
  const health = await request.get('/astrophotoflow/api/v1/health')
  expect((await health.json()).workspace.replaceAll('\\', '/').toLowerCase()).toContain('/.artifacts/workspaces/modernization-current')
  const assets = await request.get('/astrophotoflow/api/v1/library/assets?limit=1')
  const version = zAssetPage.parse(await assets.json()).items[0].current_version!
  const nodes = await request.get('/astrophotoflow/api/v1/nodes?query=autostretch')
  const capability = z.array(zNodeCapability).parse(await nodes.json()).find(node => node.operation?.operation_id === 'autostretch')!
  expect(capability.available && capability.automatic_result_preview).toBe(true)
  await page.goto('/')
  await page.waitForFunction(type => Boolean(window.app?.graph && window.LiteGraph?.registered_node_types[type]), capability.node.native_type)
  const accepted = page.waitForResponse(response => new URL(response.url()).pathname === '/api/prompt' && response.request().method() === 'POST')
  const graph = await page.evaluate(async ({ version, type }) => {
    const app = window.app
    app.api.addEventListener('executed', event => {
      if (Array.isArray(event.detail.output?.apf_result)) Reflect.set(window, Symbol.for('g7-actual-executed-result'), structuredClone(event.detail))
    })
    app.graph.clear()
    const source = window.LiteGraph.createNode('APF_DATA_REFERENCE')
    const target = window.LiteGraph.createNode(type)
    source.properties.apfAutomaticResult = false
    target.properties.apfAutomaticResult = true
    source.pos = [100, 100]; target.pos = [500, 100]
    app.graph.add(source); app.graph.add(target)
    source.widgets.find(widget => widget.name === 'reference').value = JSON.stringify({ kind: 'asset_version', asset_version_id: version, selection: { kind: 'whole_file' } })
    source.connect(0, target, target.inputs.findIndex(input => input.type === 'APF_SCIENCE'))
    await app.loadGraphData(app.graph.serialize(), true, true, null, { skipAssetScans: true })
    return { owner: app.rootGraph.id, target: String(target.id) }
  }, { version: version.id, type: capability.node.native_type })
  const response = await accepted
  expect(response.ok()).toBe(true)
  const { prompt_id } = await response.json()
  let history: Record<string, { status: { status_str: string } }> = {}
  await expect.poll(async () => {
    history = await (await request.get(`/history/${prompt_id}`)).json()
    return history[prompt_id]?.status.status_str
  }, { timeout: 60_000 }).toMatch(/^(success|error)$/)
  expect(history[prompt_id].status.status_str).toBe('success')
  const callsResponse = await request.get(`/astrophotoflow/api/v1/runs/${prompt_id}/calls?node_id=${graph.target}`)
  const calls = z.array(zSoftwareCallResult).parse(await callsResponse.json())
  expect(calls).toHaveLength(1)
  const call = calls[0]
  expect(call.state).toBe('completed')
  expect(call.workflow_id).toBe(graph.owner)
  expect(call.calculation_signature).toBeTruthy()
  const logLink = page.locator(`a[href="${call.log_url}"]`)
  await expect(logLink).toBeVisible()
  const widget = logLink.locator('..').locator('..')
  const viewer = widget.getByRole('button', { name: /打开|Open/i }).first()
  await viewer.click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  const next = await page.evaluate(async () => {
    const app = window.app
    const data = app.rootGraph.serialize()
    delete data.id
    for (const node of data.nodes) node.properties.apfAutomaticResult = false
    await app.loadGraphData(data, true, true, null, { skipAssetScans: true })
    const old = Reflect.get(window, Symbol.for('g7-actual-executed-result'))
    if (!old) throw new Error('No real native result notification captured')
    app.api.dispatchCustomEvent('executed', old)
    return { owner: app.rootGraph.id, ids: app.graph.nodes.map(node => String(node.id)) }
  })
  expect(next.owner).not.toBe(graph.owner)
  expect(next.ids).toContain(graph.target)
  await expect(page.locator(`a[href="${call.log_url}"]`)).toHaveCount(0)
  await writeFile(new URL('native-automatic-result.json', reportRoot), JSON.stringify({ graph, prompt_id, call, next, old_notification_rejected: true }, null, 2))
})

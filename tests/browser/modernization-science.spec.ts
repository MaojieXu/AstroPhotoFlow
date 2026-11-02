import { test, expect } from '../../frontend/node_modules/@playwright/test/index.mjs'
import { randomUUID, createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { z } from '../../frontend/node_modules/zod/index.js'
import { zConfigState, zDatasetOut, zNodeCapability, zDataNodeResult, zSoftwareCallResult, zExportReceipt } from '../../frontend/packages/astrophotoflow-ui/src/generated/api/zod.gen'
import { reportRoot } from './modernization-paths.mjs'
import { createSyntheticAsset } from './scientificAssets'

test.skip(process.env.APF_ALLOW_NATIVE_SCIENCE !== '1', 'Explicit opt-in required for real isolated Siril processing')

const nativeHistory = z.record(z.string(), z.object({
  status: z.object({ status_str: z.string(), messages: z.array(z.tuple([z.string(), z.unknown()])).optional() }),
  outputs: z.record(z.string(), z.object({ apf_data: z.array(zDataNodeResult).optional() })),
}))
const sha256 = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex')

test('native fixed inputs, real Siril, complete viewing and selected saving/export', async ({ page, context, request, baseURL }) => {
  test.setTimeout(180_000)
  const healthResponse = await request.get('/astrophotoflow/api/v1/health')
  expect(healthResponse.ok()).toBe(true)
  const health = await healthResponse.json()
  expect(health.workspace.replaceAll('\\', '/').toLowerCase()).toContain('/.artifacts/workspaces/modernization-current')
  const sourceId = randomUUID()
  const assets = []
  for (let index = 0; index < 3; index++) {
    assets.push(await createSyntheticAsset(request, `G7 native science ${sourceId} frame ${index}`, index))
  }
  const versions = assets.map(asset => asset.current_version!)
  expect(versions).toHaveLength(3)
  expect(versions.every(version => version?.storage_mode === 'managed')).toBe(true)
  const configResponse = await request.get('/astrophotoflow/api/v1/settings/workbench')
  expect(configResponse.ok()).toBe(true)
  const config = zConfigState.parse(await configResponse.json())
  const paths = versions.map(version => resolve(config.data_dir_absolute, version.storage_location))
  expect(paths.every(path => path.toLowerCase().startsWith(health.workspace.toLowerCase()))).toBe(true)
  const originals = await Promise.all(paths.map(async path => sha256(await readFile(path))))
  const created = await request.post('/astrophotoflow/api/v1/datasets', {
    data: { name: `G7 science ${randomUUID()}`, asset_version_ids: versions.slice(0, 2).map(version => version.id) },
  })
  expect(created.status()).toBe(201)
  const dataset = zDatasetOut.parse(await created.json())
  const reference = { kind: 'dataset_version', dataset_version_id: dataset.current_version_id,
    members: versions.slice(0, 2).map((version, member_index) => ({ member_index, asset_version_id: version.id, selection: { kind: 'whole_file' } })) }
  const nodes = await request.get('/astrophotoflow/api/v1/nodes?query=autostretch')
  expect(nodes.ok()).toBe(true)
  const capability = z.array(zNodeCapability).parse(await nodes.json()).find(node => node.operation?.operation_id === 'autostretch')!
  expect(capability.available).toBe(true)
  await context.route('**/*', route => {
    const target = new URL(route.request().url())
    return target.origin === new URL(baseURL!).origin || !['http:', 'https:'].includes(target.protocol) ? route.continue() : route.abort()
  })
  await page.goto('/')
  await page.waitForFunction(type => Boolean(window.LiteGraph?.registered_node_types[type] && window.app?.graph), capability.node.native_type)
  const graph = await page.evaluate(async ({ reference, type }) => {
    const app = window.app
    app.graph.clear()
    const source = window.LiteGraph.createNode('APF_DATA_REFERENCE')
    const software = window.LiteGraph.createNode(type)
    const result = window.LiteGraph.createNode('APF_DATA_REFERENCE')
    for (const [index, node] of [source, software, result].entries()) {
      node.properties.apfAutomaticResult = false
      node.pos = [100 + index * 350, 100]
      app.graph.add(node)
    }
    source.widgets.find(widget => widget.name === 'reference').value = JSON.stringify(reference)
    source.connect(0, software, software.inputs.findIndex(input => input.type === 'APF_SCIENCE'))
    software.connect(software.outputs.findIndex(output => output.type === 'APF_SCIENCE'), result, result.inputs.findIndex(input => input.name === 'science'))
    const workflow = await app.loadGraphData(app.graph.serialize(), true, true, null, { skipAssetScans: true })
    return { source: String(source.id), software: String(software.id), result: String(result.id), isPersisted: workflow?.isPersisted }
  }, { reference, type: capability.node.native_type })
  expect(graph.isPersisted).toBe(false)
  // A new current collection version must not change the graph's fixed version/members.
  const newer = await request.post(`/astrophotoflow/api/v1/datasets/${dataset.id}/versions`, {
    data: { base_revision: dataset.revision, asset_version_ids: versions.map(version => version.id) },
  })
  expect(newer.status()).toBe(201)
  const evidence = new URL('native-science-flow.json', reportRoot)
  const accepted = page.waitForResponse(response => new URL(response.url()).pathname === '/api/prompt' && response.request().method() === 'POST')
  expect(await page.evaluate(() => window.app.queuePrompt(0, 1))).toBe(true)
  const reply = await accepted
  expect(reply.ok()).toBe(true)
  const { prompt_id } = await reply.json()
  await writeFile(evidence, JSON.stringify({ graph, reference, prompt_id }, null, 2))
  let history: z.infer<typeof nativeHistory> = {}
  await expect.poll(async () => {
    const response = await request.get(`/history/${prompt_id}`)
    expect(response.ok()).toBe(true)
    history = nativeHistory.parse(await response.json())
    return history[prompt_id]?.status.status_str
  }, { timeout: 90_000 }).toMatch(/^(success|error)$/)
  expect(history[prompt_id].status.status_str, JSON.stringify(history[prompt_id].status)).toBe('success')
  const result = history[prompt_id].outputs[graph.result].apf_data![0]
  expect(result.state).toBe('completed')
  const callsResponse = await request.get(`/astrophotoflow/api/v1/runs/${prompt_id}/calls?node_id=${graph.software}`)
  expect(callsResponse.ok()).toBe(true)
  const calls = z.array(zSoftwareCallResult).parse(await callsResponse.json())
  expect(calls).toHaveLength(1)
  const call = calls[0]
  expect(call.state).toBe('completed')
  expect(call.software_version).toBe('1.4.4')
  expect(call.observation?.active).toBe(false)
  const port = call.ports.find(port => port.name === 'image')!
  expect(port.members).toHaveLength(2)
  const selected = await request.get(port.members[1].file_url)
  expect(selected.ok()).toBe(true)
  const selectedHash = sha256(await selected.body())
  const source = { run_id: prompt_id, execution_id: result.execution_id }
  async function exportSelected(target: 'library' | 'local', destination?: string) {
    const request_id = randomUUID()
    const response = await request.post('/astrophotoflow/api/v1/exports', {
      data: { request_id, source, member_indexes: [1], target, ...(destination ? { destination } : {}), settings: { format: 'original' } },
    })
    expect(response.status()).toBe(202)
    let receipt = zExportReceipt.parse(await response.json())
    await expect.poll(async () => {
      const response = await request.get(`/astrophotoflow/api/v1/exports/${request_id}`)
      expect(response.ok()).toBe(true)
      receipt = zExportReceipt.parse(await response.json())
      return receipt.state
    }, { timeout: 60_000 }).toBe('completed')
    expect(receipt.results).toHaveLength(1)
    expect(receipt.results[0].member_index).toBe(1)
    return receipt
  }
  const saved = await exportSelected('library')
  expect(saved.results[0].registration?.asset_version_id).toBeTruthy()
  const destination = resolve(health.workspace, 'output', `g7-selected-${randomUUID()}.fit`)
  const exported = await exportSelected('local', destination)
  expect(sha256(await readFile(destination))).toBe(selectedHash)
  expect(await Promise.all(paths.map(async path => sha256(await readFile(path))))).toEqual(originals)
  await writeFile(evidence, JSON.stringify({ graph, reference, prompt_id, history, call, saved, exported, originals_unchanged: true, selected_sha256: selectedHash }, null, 2))
})

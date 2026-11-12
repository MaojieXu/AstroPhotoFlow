import { test, expect } from '../../frontend/node_modules/@playwright/test/index.mjs'
import { writeFile } from 'node:fs/promises'
import { z } from '../../frontend/node_modules/zod/index.js'
import { zDataNodeResult } from '../../frontend/packages/astrophotoflow-ui/src/generated/api/zod.gen'
import { reportRoot } from './modernization-paths.mjs'

const nativeHistory = z.record(z.string(), z.object({
  status: z.object({ status_str: z.string() }),
  outputs: z.record(z.string(), z.object({ apf_data: z.array(zDataNodeResult).optional() })),
}))

test.skip(process.env.APF_ALLOW_NATIVE_QUEUE !== '1', 'Explicit opt-in required for the isolated native queue')

test('unpersisted native draft executes fixed Data input through the real queue', async ({ page, context, request, baseURL }) => {
  const health = await request.get('/astrophotoflow/api/v1/health')
  expect(health.ok()).toBe(true)
  expect((await health.json()).workspace.replaceAll('\\', '/').toLowerCase()).toContain('/.artifacts/workspaces/modernization-current')
  const assets = await request.get('/astrophotoflow/api/v1/library/assets?limit=1')
  expect(assets.ok()).toBe(true)
  const version = (await assets.json()).items[0].current_version
  expect(version.storage_mode).toBe('managed')
  const errors: string[] = []
  page.on('pageerror', error => errors.push(String(error)))
  await context.route('**/*', route => {
    const url = new URL(route.request().url())
    return url.origin === new URL(baseURL!).origin || !['http:', 'https:'].includes(url.protocol) ? route.continue() : route.abort()
  })
  await page.goto('/')
  await page.waitForFunction(() => Boolean(window.app?.graph && window.LiteGraph?.registered_node_types.APF_DATA_REFERENCE))
  const reference = { kind: 'asset_version', asset_version_id: version.id, selection: { kind: 'whole_file' } }
  const draft = await page.evaluate(async reference => {
    const app = window.app
    app.graph.clear()
    const node = window.LiteGraph.createNode('APF_DATA_REFERENCE')
    app.graph.add(node)
    node.widgets.find(widget => widget.name === 'reference').value = JSON.stringify(reference)
    const workflow = await app.loadGraphData(app.graph.serialize(), true, true, null, { skipAssetScans: true })
    return { isPersisted: workflow?.isPersisted, path: workflow?.path }
  }, reference)
  expect(draft.isPersisted).toBe(false)
  const queue = await request.get('/queue')
  expect(await queue.json()).toEqual({ queue_running: [], queue_pending: [] })
  const accepted = page.waitForResponse(response => new URL(response.url()).pathname === '/api/prompt' && response.request().method() === 'POST')
  const queued = await page.evaluate(() => window.app.queuePrompt(0, 1))
  expect(queued).toBe(true)
  const reply = await accepted
  expect(reply.ok()).toBe(true)
  const { prompt_id } = await reply.json()
  let history: z.infer<typeof nativeHistory> = {}
  await expect.poll(async () => {
    const response = await request.get(`/history/${prompt_id}`)
    expect(response.ok()).toBe(true)
    history = nativeHistory.parse(await response.json())
    return history[prompt_id]?.status?.status_str
  }).toBe('success')
  const outputs = Object.values(history[prompt_id].outputs)
  expect(outputs.some(output => output.apf_data?.some(result => result.state === 'completed'))).toBe(true)
  expect(errors).toEqual([])
  await writeFile(new URL('native-unpersisted-draft.json', reportRoot), JSON.stringify({ draft, prompt_id, history }, null, 2))
})

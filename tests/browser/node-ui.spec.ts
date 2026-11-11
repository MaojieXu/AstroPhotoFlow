import { createHash, randomUUID } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { isAbsolute, join, relative } from 'node:path'

import { test, expect } from './native.fixtures'
import { createSyntheticAsset } from './scientificAssets'
import { zSoftwareCallResult } from '../../frontend/packages/astrophotoflow-ui/src/generated/api/zod.gen'

test('compact nodes import selected paths, reset with one undo and switch channels without another execution', async ({
  page, request, isolatedWorkspace
}) => {
  test.setTimeout(120_000)
  const asset = await createSyntheticAsset(request, 'node-ui-' + randomUUID(), 0, 3)
  const sourcePath = isAbsolute(asset.storage_location)
    ? asset.storage_location : join(isolatedWorkspace, 'data', asset.storage_location)
  expect(relative(isolatedWorkspace, sourcePath).startsWith('..')).toBe(false)
  const sourceBytes = await readFile(sourcePath)
  await page.route('**/api/v1/imports/select-local', route => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ cancelled: false, folder: false, name: asset.name,
      files: [{ path: sourcePath, name: asset.name, size: sourceBytes.length }] })
  }))
  let queued = 0
  page.on('request', request => {
    if (request.method() === 'POST' && new URL(request.url()).pathname.endsWith('/prompt')) queued++
  })
  await page.goto('/')
  await expect(page.locator('#graph-canvas')).toBeVisible()
  const type = 'APF_169de0837f814cdea3295541ecacf463'
  await page.waitForFunction(type => Boolean(window.LiteGraph.registered_node_types[type]), type)
  await page.waitForFunction(() => Boolean(window.app?.isGraphReady && window.app.graph))
  await page.getByRole('button', { name: '关闭侧边栏', exact: true }).click()
  const ids = await page.evaluate(async type => {
    const graph = window.app.graph
    graph.clear()
    const source = window.LiteGraph.createNode('APF_DATA_REFERENCE')
    source.pos = [350, 120]
    source.title = 'My source'
    source.properties.apfAutomaticResult = false
    source.size = [300, 800]
    graph.add(source)
    const tool = window.LiteGraph.createNode(type)
    tool.pos = [760, 120]
    tool.title = 'My processing'
    tool.properties.apfAutomaticResult = false
    tool.size = [350, 800]
    tool.widgets.find(widget => widget.name === 'targetbg').value = 0.6
    tool.widgets.find(widget => widget.name === 'linked').value = true
    tool.widgets.find(widget => widget.name === 'runtime').value = '{"threads":1}'
    graph.add(tool)
    source.connect(0, tool, 0)
    const data = graph.serialize()
    await window.app.loadGraphData(data)
    return [source.id, tool.id]
  }, type)
  const source = page.locator(`[data-node-id="${ids[0]}"]`)
  const tool = page.locator(`[data-node-id="${ids[1]}"]`)
  await source.getByRole('button', { name: '导入', exact: true }).click()
  await expect(source.getByRole('button', { name: '更换文件', exact: true })).toBeVisible()
  await source.getByRole('button', { name: '手动输入文件路径' }).click()
  await expect(source.getByRole('textbox', { name: '图像文件绝对路径' })).toHaveValue(sourcePath)
  await source.getByRole('button', { name: '手动输入文件路径' }).click()
  const readGraph = () => page.evaluate(ids => {
    const graph = window.app.graph
    const source = graph.getNodeById(ids[0])
    const tool = graph.getNodeById(ids[1])
    return { reference: source.widgets.find(widget => widget.name === 'reference').value,
      values: Object.fromEntries(tool.widgets.filter(widget => ['targetbg', 'linked', 'runtime'].includes(widget.name))
        .map(widget => [widget.name, widget.value])), title: tool.title, sourceTitle: source.title,
      positions: [Array.from(source.pos), Array.from(tool.pos)], sizes: [Array.from(source.size), Array.from(tool.size)], links: graph.serialize().links }
  }, ids)
  await expect.poll(async () => JSON.parse((await readGraph()).reference).kind).toBe('asset')
  expect((await readGraph()).sourceTitle).toBe('My source')
  expect(queued).toBe(0)
  const submitted = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/prompt'))
  expect(await page.evaluate(() => window.app.queuePrompt(0, 1))).toBe(true)
  const prompt = await (await submitted).json()
  let call: ReturnType<typeof zSoftwareCallResult.parse> | undefined
  await expect.poll(async () => {
    const response = await request.get(`/astrophotoflow/api/v1/runs/${prompt.prompt_id}/calls`)
    expect(response.ok()).toBe(true)
    call = zSoftwareCallResult.array().parse(await response.json()).find(item => item.node_id === String(ids[1]))
    return call?.state
  }).toBe('completed')
  await expect(tool.getByTestId('node-channel-select')).toBeVisible()
  await expect(source.getByRole('button', { name: '保存到素材库' })).toBeVisible()
  await expect(source.getByRole('button', { name: '导出到本机' })).toBeVisible()
  await expect(source.getByRole('button', { name: '下一张图像' })).toHaveCount(0)
  await expect(tool.getByText('result.fit', { exact: true })).toHaveCount(0)
  await expect(tool.getByRole('link', { name: '日志' })).toHaveCount(0)
  await expect(tool.getByRole('link', { name: '下载完整文件' })).toHaveCount(0)
  await tool.getByRole('button', { name: '更多操作' }).click()
  await expect(page.getByRole('menuitem', { name: '日志', exact: true })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: '下载完整文件', exact: true })).toHaveAttribute('href', call!.ports[0].members[0].file_url)
  await page.keyboard.press('Escape')
  await source.getByRole('button', { name: '详情', exact: true }).click()
  await expect(page.getByRole('dialog').getByText(sourcePath, { exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(tool.getByRole('textbox', { name: '运行配置 JSON' })).toHaveCount(0)
  await tool.getByRole('button', { name: '显示高级输入', exact: true }).click()
  await expect(tool.getByRole('textbox', { name: '运行配置 JSON' })).toBeVisible()
  await tool.getByRole('button', { name: '隐藏高级输入', exact: true }).click()
  const snapshot = await readGraph()
  const history = await (await request.get('/history')).json()
  const file = call!.ports[0].members[0].file_url
  const digest = (buffer: Buffer) => createHash('sha256').update(buffer).digest('hex')
  const original = digest(await (await request.get(file)).body())
  for (const channel of ['R', 'G', 'B', 'RGB']) {
    await tool.getByTestId('node-channel-select').click()
    await page.getByRole('option', { name: channel, exact: true }).click()
    await expect(tool.getByTestId('node-channel-select')).toHaveText(channel)
  }
  expect(queued).toBe(1)
  expect(await (await request.get('/history')).json()).toEqual(history)
  expect(digest(await (await request.get(file)).body())).toBe(original)
  expect(await readGraph()).toEqual(snapshot)
  await tool.getByRole('button', { name: '恢复默认参数' }).click()
  await expect.poll(async () => (await readGraph()).values).toEqual({ targetbg: 0.25, linked: false, runtime: '{}' })
  const reset = await readGraph()
  expect(reset.reference).toBe(snapshot.reference)
  expect(reset.links).toEqual(snapshot.links)
  expect(reset.title).toBe(snapshot.title)
  expect(reset.positions).toEqual(snapshot.positions)
  await expect(tool.getByRole('button', { name: '恢复默认参数' })).toBeDisabled()
  await page.keyboard.press('Control+z')
  await expect.poll(async () => (await readGraph()).values).toEqual(snapshot.values)
  expect(queued).toBe(1)
  await expect.poll(async () => (await source.boundingBox())!.height).toBeLessThan(650)
  await expect.poll(async () => (await tool.boundingBox())!.height).toBeLessThan(650)
  const autoQueued = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/prompt'))
  await page.evaluate(ids => {
    for (const id of ids) window.app.graph.getNodeById(id).properties.apfAutomaticResult = true
    window.comfyAPI.api.api.dispatchCustomEvent('graphChanged', null)
  }, ids)
  const automaticPrompt = await (await autoQueued).json()
  await expect.poll(async () => {
    const calls = await (await request.get(`/astrophotoflow/api/v1/runs/${automaticPrompt.prompt_id}/calls`)).json()
    return calls.find(item => item.node_id === String(ids[1]))?.state
  }).toBe('completed')
  await expect(tool.getByRole('button', { name: '恢复默认参数' })).toBeEnabled()
  const resetQueued = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/prompt'))
  await tool.getByRole('button', { name: '恢复默认参数' }).click()
  await expect.poll(async () => (await readGraph()).values).toEqual({ targetbg: 0.25, linked: false, runtime: '{}' })
  const resetPrompt = await (await resetQueued).json()
  await expect.poll(async () => {
    const calls = await (await request.get(`/astrophotoflow/api/v1/runs/${resetPrompt.prompt_id}/calls`)).json()
    return calls.find(item => item.node_id === String(ids[1]))?.state
  }).toBe('completed')
  await expect.poll(async () => {
    const queue = await (await request.get('/queue')).json()
    return queue.queue_running.length + queue.queue_pending.length
  }).toBe(0)
  expect(queued).toBe(3)
  expect(digest(await readFile(sourcePath))).toBe(digest(sourceBytes))
  await expect(tool.getByTestId('node-channel-select')).toBeVisible()
  const preview = tool.getByRole('img', { name: 'result.fit', exact: true })
  await expect(preview).toBeVisible()
  await expect.poll(async () => preview.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBe(true)
  await page.screenshot({ path: join(process.env.APF_BROWSER_REPORT!, 'compact-nodes.png') })
})

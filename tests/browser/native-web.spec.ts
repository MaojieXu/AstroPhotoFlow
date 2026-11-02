import { readFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { parse, resolve, relative } from 'node:path'
import { uploadAssetBytes } from './scientificAssets'
import { test, expect, openSidebar } from './native.fixtures'
import {
  zConfigState,
  zProjectOut,
  zServiceHealth
} from '../../frontend/packages/astrophotoflow-ui/src/generated/api/zod.gen'

test('native sidebar ordering, authenticated proxy and close/reopen retain the canvas', async ({
  page,
  request
}) => {
  await page.goto('/')
  await expect(page.getByTestId('library-sidebar')).toBeVisible()
  await expect(page).toHaveURL(/#\/workflows$/)
  await expect(page.locator('#graph-canvas')).toBeVisible()
  const ids = await page
    .getByTestId('sidebar-top-group')
    .locator("button[data-testid$='-tab-button']")
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute('data-testid'))
    )
  expect(ids.indexOf('node-library-tab-button')).toBeLessThan(
    ids.indexOf('library-tab-button')
  )
  expect(ids.indexOf('library-tab-button')).toBeLessThan(
    ids.indexOf('workflows-tab-button')
  )
  const panel = await page.getByTestId('library-sidebar').boundingBox()
  const frame = await page.locator('.graph-canvas-panel').boundingBox()
  expect(panel!.width).toBeLessThan(page.viewportSize()!.width / 2)
  expect(frame!.width).toBeGreaterThan(300)
  expect(frame!.x).toBeGreaterThanOrEqual(panel!.x + panel!.width - 2)
  const response = await request.get('/astrophotoflow/api/v1/health')
  expect(zServiceHealth.parse(await response.json()).schema_revision).toBe(
    '0001_baseline'
  )
  expect(response.headers()['x-request-id']).toBeTruthy()
  expect(response.headers().authorization).toBeUndefined()
  await page
    .getByTestId('library-sidebar')
    .getByTestId('sidebar-close-button')
    .click()
  await expect(page.getByTestId('library-sidebar')).toHaveCount(0)
  await expect(page.locator('#graph-canvas')).toBeVisible()
  await openSidebar(page, 'library')
  await page.reload()
  await expect(page.getByTestId('library-sidebar')).toBeVisible()
  await expect(page.locator('#graph-canvas')).toBeVisible()
})

test('project creation and unsaved navigation protect native graph and viewport', async ({
  page,
  request
}) => {
  const name = 'G7 project ' + randomUUID()
  let projectId: string | undefined
  await page.goto('/')
  await page.waitForFunction(() => Boolean(window.app?.graph))
  const snapshot = () =>
    page.evaluate(() => ({
      nodes: window.app.graph.serialize().nodes,
      scale: window.app.canvas.ds.scale,
      offset: Array.from(window.app.canvas.ds.offset)
    }))
  const original = await page.evaluate(() => window.app.graph.serialize())
  await page.evaluate(async () => {
    await window.app.reloadNodeDefs()
    window.app.graph.clear()
    const a = window.LiteGraph.createNode('LoadImage'),
      b = window.LiteGraph.createNode('SaveImage')
    a.pos = [460, 160]
    b.pos = [820, 160]
    window.app.graph.add(a)
    window.app.graph.add(b)
    a.connect(0, b, 0)
    window.app.canvas.ds.scale = 0.8
    window.app.canvas.ds.offset = [34, 56]
  })
  const before = await snapshot()
  expect(before.nodes).toHaveLength(2)
  try {
    await openSidebar(page, 'projects')
    const workspace = page.locator('.apf-workspace')
    await workspace
      .getByRole('button', { name: '新建项目', exact: true })
      .click()
    const form = page.getByRole('form', { name: '记录编辑表单', exact: true })
    await form.locator('#project-name').fill(name)
    const saved = page.waitForResponse(
      (r) =>
        r.request().method() === 'POST' &&
        new URL(r.url()).pathname.endsWith('/api/v1/projects')
    )
    await form.getByRole('button', { name: '保存', exact: true }).click()
    const response = await saved
    expect(response.status()).toBe(201)
    projectId = zProjectOut.parse(await response.json()).id
    await expect(workspace).toContainText(name)
    await workspace
      .getByRole('button', { name: '新建项目', exact: true })
      .click()
    await form.locator('#project-name').fill('G7 unsaved project')
    page.once('dialog', (dialog) => dialog.dismiss())
    await page.getByTestId('workflows-tab-button').click()
    await expect(page.getByTestId('projects-sidebar')).toBeVisible()
    await expect(form.locator('#project-name')).toHaveValue(
      'G7 unsaved project'
    )
    page.once('dialog', (dialog) => dialog.accept())
    await openSidebar(page, 'workflows')
    const tools = await page.getByTestId('side-toolbar').boundingBox()
    expect(tools!.x).toBeLessThan(64)
    expect(tools!.width).toBeLessThanOrEqual(64)
    expect((await page.locator('.graph-canvas-panel').boundingBox())!.x).toBeGreaterThanOrEqual(64)
    await openSidebar(page, 'node-library')
    await openSidebar(page, 'library')
    await page
      .locator('.apf-workspace')
      .getByRole('button', { name: '设备管理', exact: true })
      .click()
    await openSidebar(page, 'workflows')
    expect(await snapshot()).toEqual(before)
  } finally {
    await page.evaluate(
      async (graph) => window.app.loadGraphData(graph),
      original
    )
    if (projectId) {
      const current = zProjectOut.parse(
        await (
          await request.get('/astrophotoflow/api/v1/projects/' + projectId)
        ).json()
      )
      const archived = await request.patch(
        '/astrophotoflow/api/v1/projects/' + projectId,
        { data: { base_revision: current.revision, status: 'archived' } }
      )
      expect(archived.status()).toBe(200)
    }
  }
})

test('binary upload, full preview and trash restore preserve original bytes across reload', async ({
  page,
  request,
  isolatedWorkspace
}) => {
  const image = await readFile(
    new URL('../fixtures/native-web.png', import.meta.url)
  )
  const filename = 'G7-web-' + randomUUID() + '.png',
    name = parse(filename).name
  const asset = await uploadAssetBytes(request, filename, image)
  await page.goto('/')
  const row = page
    .locator('.apf-assets-table tbody tr')
    .filter({ hasText: name })
  await expect(row.locator('.apf-thumb img')).toBeVisible({ timeout: 30_000 })
  await row
    .getByRole('button', { name: `查看 ${name} 大图`, exact: true })
    .click()
  const preview = page.getByRole('dialog')
  await expect(preview).toBeVisible()
  await expect(preview.locator('canvas').first()).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(preview).toHaveCount(0)
  const api = '/astrophotoflow/api/v1'
  const removed = await request.delete(api + '/library/items', {
    data: {
      items: [
        {
          entry_type: 'asset',
          id: asset.id,
          revision: asset.revision,
          current_version_id: asset.current_version_id
        }
      ]
    }
  })
  expect(removed.status()).toBe(200)
  const trash = await (await request.get(api + '/library/trash')).json()
  const item = trash.items.find(
    (entry: { id: string }) => entry.id === asset.id
  )
  const selection = Object.fromEntries(
    [
      'entry_type',
      'id',
      'removed_at',
      'revision',
      'current_version_id',
      'source_dataset_id'
    ].map((key) => [key, item[key]])
  )
  expect(
    (
      await request.post(api + '/library/trash/restore', {
        data: { items: [selection] }
      })
    ).status()
  ).toBe(200)
  await page.reload()
  await expect(row).toBeVisible()
  expect(
    await readFile(new URL('../fixtures/native-web.png', import.meta.url))
  ).toEqual(image)
  const config = zConfigState.parse(
    await (await request.get(api + '/settings/workbench')).json()
  )
  const original = resolve(
    config.data_dir_absolute,
    asset.current_version!.storage_location
  )
  expect(relative(isolatedWorkspace, original).startsWith('..')).toBe(false)
  expect(await readFile(original)).toEqual(image)
})

test('native image workflow saves, reloads and executes through the original queue', async ({
  page,
  request
}) => {
  test.skip(
    process.env.APF_ALLOW_NATIVE_QUEUE !== '1',
    'Explicit opt-in required for the isolated native queue'
  )
  await page.goto('/')
  await page.waitForFunction(() => Boolean(window.app?.graph))
  const image = await readFile(
    new URL('../fixtures/native-web.png', import.meta.url)
  )
  const name = 'G7-native-' + randomUUID()
  const upload = await request.post('/api/upload/image', {
    multipart: {
      image: { name: name + '.png', mimeType: 'image/png', buffer: image }
    }
  })
  expect(upload.status()).toBe(200)
  const source = (await upload.json()).name
  const original = await page.evaluate(() => window.app.graph.serialize())
  try {
    await page.evaluate(
      async ({ source, name }) => {
        await window.app.reloadNodeDefs()
        window.app.graph.clear()
        const input = window.LiteGraph.createNode('LoadImage'),
          output = window.LiteGraph.createNode('SaveImage')
        input.widgets.find((widget) => widget.name === 'image').value = source
        output.widgets.find(
          (widget) => widget.name === 'filename_prefix'
        ).value = name
        window.app.graph.add(input)
        window.app.graph.add(output)
        input.connect(0, output, 0)
      },
      { source, name }
    )
    const graph = await page.evaluate(() => window.app.graph.serialize())
    const path =
      '/api/userdata/' + encodeURIComponent('workflows/' + name + '.json')
    expect((await request.post(path, { data: graph })).status()).toBe(200)
    const loaded = await request.get(path)
    expect(loaded.status()).toBe(200)
    expect((await loaded.json()).nodes).toEqual(graph.nodes)
    await page.evaluate(
      async (graph) => window.app.loadGraphData(graph),
      await loaded.json()
    )
    const receipt = await page.evaluate(async () =>
      window.comfyAPI.api.api.queuePrompt(0, await window.app.graphToPrompt())
    )
    await expect
      .poll(
        async () => {
          const response = await request.get(
            '/api/history/' + receipt.prompt_id
          )
          return (await response.json())[receipt.prompt_id]?.status?.status_str
        },
        { timeout: 30_000 }
      )
      .toBe('success')
  } finally {
    await page.evaluate(
      async (graph) => window.app.loadGraphData(graph),
      original
    )
  }
})

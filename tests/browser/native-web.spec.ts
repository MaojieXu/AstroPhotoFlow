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

test('local workbench exposes its own brand and hides upstream product entry points', async ({
  page,
  request
}) => {
  await page.goto('/')
  await expect(page.locator('#graph-canvas')).toBeVisible()
  await expect(page.getByTestId('login-button')).toHaveCount(0)
  const favicon = page.locator('link[rel="icon"]')
  await expect(favicon).toHaveAttribute('href', /astrophotoflow.*\.svg/)
  for (const event of ['execution_success', 'execution_interrupted']) {
    const promptId = randomUUID()
    await page.evaluate((id) => {
      window.comfyAPI.api.api.dispatchEvent(
        new CustomEvent('execution_start', { detail: { prompt_id: id } })
      )
    }, promptId)
    await expect(favicon).toHaveAttribute('href', /^data:image\/svg\+xml,/)
    await page.evaluate(({ event, promptId }) => {
      window.comfyAPI.api.api.dispatchEvent(
        new CustomEvent(event, { detail: { prompt_id: promptId } })
      )
    }, { event, promptId })
    await expect(favicon).toHaveAttribute('href', /astrophotoflow.*\.svg/)
  }
  const manifestUrl = await page.locator('link[rel="manifest"]').getAttribute('href')
  expect(manifestUrl).toBeTruthy()
  const manifest = await (await request.get(manifestUrl!)).json()
  expect(manifest.name).toBe('AstroPhotoFlow')
  for (const icon of manifest.icons) {
    const response = await request.get(icon.src)
    expect(response.ok()).toBe(true)
    expect(response.headers()['content-type']).toContain('image/png')
  }
  await page.getByTestId('help-center-button').click()
  await expect(page.getByRole('menuitem')).toHaveText([
    '使用文档', '问题反馈', '关于 AstroPhotoFlow'
  ])
  await page.keyboard.press('Escape')
  await page.getByTestId('comfy-menu-button').click()
  await page.getByRole('menuitem', { name: '视图', exact: true }).press('ArrowRight')
  await expect(page.getByRole('menuitem', { name: '浏览模板' })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await page.keyboard.press('Escape')
  await openSidebar(page, 'node-library')
  await expect(page.getByRole('tab', { name: '全部节点', exact: true })).toBeVisible()
  await expect(page.getByRole('tab', { name: '基础', exact: true })).toHaveCount(0)
})

test('a local workbench still reports missing nodes in a legacy workflow', async ({
  page
}) => {
  await page.goto('/')
  await expect(page.locator('#graph-canvas')).toBeVisible()
  await page.waitForFunction(() => Boolean(window.app?.graph))
  const workflow = JSON.parse(
    await readFile(
      new URL('../../frontend/browser_tests/assets/missing/missing_nodes.json', import.meta.url),
      'utf8'
    )
  )
  await page.evaluate((graph) => window.app.loadGraphData(graph), workflow)
  const overlay = page.getByTestId('error-overlay')
  await expect(overlay).toBeVisible()
  await overlay.getByTestId('error-overlay-see-errors').click()
  await expect(page.getByTestId('missing-node-card')).toContainText('UNKNOWN NODE')
  await expect(page.locator('#graph-canvas')).toBeVisible()
})

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
    '0001_subframe_library'
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

  const library = page.getByTestId('library-sidebar')
  const calibrationTab = library.getByText('校准库', { exact: true })
  await expect(calibrationTab).toHaveCount(1)
  await calibrationTab.click()
  await expect(calibrationTab).toHaveCount(1)
  await expect(
    library.getByRole('button', { name: '从已有校准照片创建组', exact: true })
  ).toHaveCount(0)

  await openSidebar(page, 'projects')
  const projects = page.getByTestId('projects-sidebar')
  await expect(projects.getByText('项目', { exact: true })).toHaveCount(1)
  await expect(projects.getByRole('button', { name: '新建项目' })).toBeVisible()
})

test('equipment dropdowns dismiss before a device or setup editor opens', async ({ page }) => {
  await page.goto('/')
  const library = page.getByTestId('library-sidebar')
  await library.getByRole('button', { name: '设备管理', exact: true }).click()
  await library.getByRole('tab', { name: '我的设备', exact: true }).click()

  const category = library.getByRole('combobox', { name: '设备类别' })
  const categories = page.getByRole('listbox', { includeHidden: true }).filter({
    has: page.getByRole('option', { name: '全部设备', exact: true, includeHidden: true })
  })
  const createDevice = library.getByRole('button', { name: '新建设备', exact: true, includeHidden: true })
  await category.click()
  await expect(categories).toBeVisible()
  await createDevice.click()
  await expect(page.getByRole('heading', { name: '新建设备', exact: true })).toBeVisible()
  await expect(categories).toBeHidden()
  await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click()
  await expect(category).toHaveAttribute('aria-expanded', 'false')

  const menu = page.getByRole('menu', { name: '更多操作', includeHidden: true })
  const more = library.getByRole('button', { name: '更多操作', exact: true, includeHidden: true })
  await category.click()
  await expect(categories).toBeVisible()
  await more.click()
  await expect(menu).toBeVisible()
  await expect(categories).toBeHidden()
  await category.click()
  await expect(categories).toBeVisible()
  await expect(menu).toBeHidden()
  await expect(more).not.toBeFocused()
  await page.keyboard.press('Escape')
  await expect(categories).toBeHidden()
  await expect(category).toBeFocused()
  await more.click()
  await expect(menu).toBeVisible()
  await createDevice.click()
  await expect(menu).toBeHidden()
  await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click()

  await library.getByRole('tab', { name: '设备组合', exact: true }).click()
  await more.click()
  await expect(menu).toBeVisible()
  await library.getByRole('button', { name: '新建设备组合', exact: true, includeHidden: true }).click()
  await expect(page.getByRole('heading', { name: '新建设备组合', exact: true })).toBeVisible()
  await expect(menu).toBeHidden()
})

test('library and project toolbar popups close when their view changes', async ({ page }) => {
  await page.goto('/')
  const library = page.getByTestId('library-sidebar')
  const importButton = library.getByRole('button', { name: '导入', exact: true })
  const selectFiles = library.getByRole('button', { name: '选择文件', exact: true })
  await importButton.click()
  await expect(selectFiles).toBeVisible()
  await library.getByRole('tab', { name: '亮场', exact: true }).click()
  await expect(selectFiles).toHaveCount(0)

  const libraryFilters = library.getByRole('region', { name: '素材筛选' })
  await library.getByRole('button', { name: '筛选', exact: true }).click()
  await expect(libraryFilters).toBeVisible()
  await library.getByRole('tab', { name: '校准库', exact: true }).click()
  await expect(libraryFilters).toHaveCount(0)

  const menu = page.getByRole('menu', { name: '更多操作', includeHidden: true })
  await library.getByRole('button', { name: '更多操作', exact: true }).click()
  await expect(menu).toBeVisible()
  await library.getByRole('tab', { name: '全部素材', exact: true, includeHidden: true }).click()
  await expect(menu).toBeHidden()

  await importButton.click()
  await library.getByRole('button', { name: '设备管理', exact: true }).click()
  await library.getByRole('button', { name: '返回素材库', exact: true }).click()
  await expect(selectFiles).toHaveCount(0)

  await openSidebar(page, 'projects')
  const projects = page.getByTestId('projects-sidebar')
  const targetFilter = projects.getByPlaceholder('按目标筛选')
  await projects.getByRole('button', { name: '筛选', exact: true }).click()
  await expect(targetFilter).toBeVisible()
  await projects.getByRole('button', { name: '新建项目', exact: true }).click()
  await expect(projects.getByRole('heading', { name: '创建项目', exact: true })).toBeVisible()
  await expect(targetFilter).toHaveCount(0)
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


test('filter Channel saves free text and can be cleared without renaming the device', async ({ page, request }) => {
  const name = 'Manager filter ' + randomUUID()
  await page.goto('/')
  await expect(page.getByTestId('library-sidebar')).toBeVisible()
  await page.getByRole('button', { name: '设备管理', exact: true }).click()
  await page.getByRole('button', { name: '新建设备组合', exact: true }).click()
  await page.getByRole('button', { name: '新建滤镜', exact: true }).click()
  const form = page.getByRole('form', { name: '新建设备表单' })
  await form.getByLabel('设备名称', { exact: true }).fill(name)
  const channel = form.getByLabel('Channel（通道）', { exact: true })
  await expect(channel).toHaveAttribute('type', 'text')
  await expect(channel).not.toHaveAttribute('list', /.+/)
  await channel.fill('Custom Ha')
  await form.getByLabel('带宽', { exact: true }).fill('7')
  await expect(form.getByLabel('组合标签预览', { exact: true })).toHaveText('Custom Ha 7nm')
  await form.getByRole('button', { name: '保存设备并加入', exact: true }).click()
  await expect(form).toHaveCount(0)
  const response = await request.get('/astrophotoflow/api/v1/equipment?limit=200')
  expect(response.ok()).toBeTruthy()
  const devices = (await response.json()).items
  const device = devices.find((item: { name: string }) => item.name === name)
  expect(device).toMatchObject({ kind: 'filter', name, specs: { channel: 'Custom Ha', bandwidth_nm: 7 } })
  const cleared = await request.patch('/astrophotoflow/api/v1/equipment/' + device.id, {
    data: { kind: 'filter', base_revision: device.revision, specs: { channel: null } }
  })
  expect(cleared.ok()).toBeTruthy()
  expect(await cleared.json()).toMatchObject({ id: device.id, name, specs: { channel: null, bandwidth_nm: 7 } })
})

import { test, expect, openWorkbenchSettings } from './native.fixtures'
import { zConfigState } from '../../frontend/packages/astrophotoflow-ui/src/generated/api/zod.gen'

test('native settings stay searchable, reject non-loopback host and keep the canvas', async ({
  page,
  request
}) => {
  await openWorkbenchSettings(page)
  const panel = page.getByTestId('workbench-settings')
  const initial = zConfigState.parse(
    await (
      await request.get('/astrophotoflow/api/v1/settings/workbench')
    ).json()
  )
  const workspaceSettings = panel.getByRole('region', {
    name: '工作区、端口和目录'
  })
  const workspacePath = workspaceSettings.getByRole('textbox', {
    name: '默认工作区'
  })
  const host = workspaceSettings.getByRole('textbox', { name: '服务主机' })
  await expect(workspacePath).toBeVisible()
  await expect(
    workspaceSettings.getByRole('textbox', { name: '数据目录' })
  ).toBeVisible()
  await expect(host).toBeVisible()
  await expect(
    workspaceSettings.getByRole('spinbutton', { name: '首选服务端口' })
  ).toBeVisible()
  expect((await workspacePath.boundingBox())!.width).toBeGreaterThan(
    (await host.boundingBox())!.width
  )
  expect(await panel.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(
    false
  )
  await host.fill('0.0.0.0')
  await panel.getByRole('button', { name: '保存配置', exact: true }).click()
  await expect(panel.getByRole('alert')).toBeVisible()
  const unchanged = zConfigState.parse(
    await (
      await request.get('/astrophotoflow/api/v1/settings/workbench')
    ).json()
  )
  expect(unchanged.saved.host).toBe(initial.saved.host)
  await panel.getByRole('button', { name: '重新读取配置', exact: true }).click()
  await expect(panel.getByRole('alert')).toHaveCount(0)
  const dialog = page.getByTestId('settings-dialog')
  const search = dialog.getByPlaceholder('搜索设置...')
  for (const term of [
    'Comfy.Execution.PreviewMethod',
    'Comfy.EditAttention.Delta',
    'Comfy.NodeBadge.ShowApiPricing',
    'Comfy.ModelLibrary.AutoLoadAll',
    'Comfy.ModelLibrary.NameFormat',
    'Comfy.DevMode',
    '3D'
  ]) {
    await search.fill(term)
    await expect(dialog.getByText('未找到结果', { exact: true })).toBeVisible()
    await expect(dialog.locator('[data-setting-id]')).toHaveCount(0)
  }
  await search.fill('工作台')
  await expect(
    dialog.getByRole('heading', { name: '工作台配置', exact: true })
  ).toBeVisible()
  await search.fill('语言')
  await expect(dialog.locator('[data-setting-id="Comfy.Locale"]')).toBeVisible()
  await search.fill('')
  await dialog.getByText('工作台', { exact: true }).first().click()
  await dialog.getByRole('button', { name: '关闭对话框', exact: true }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.locator('#graph-canvas')).toBeVisible()
})

test('configuration conflict retains the draft; native restart adopts and restores saved values', async ({
  page,
  context,
  request,
  baseURL
}) => {
  test.skip(
    process.env.APF_ALLOW_WORKBENCH_RESTART !== '1',
    'Explicit opt-in required to restart the selected private workbench'
  )
  test.setTimeout(240_000)
  const path = '/astrophotoflow/api/v1/settings/workbench'
  const initial = zConfigState.parse(await (await request.get(path)).json())
  expect(
    initial.restart_required,
    'Begin with no unrelated pending configuration'
  ).toBe(false)
  const queue = await (await request.get('/queue')).json()
  expect(queue.queue_running).toHaveLength(0)
  expect(queue.queue_pending).toHaveLength(0)
  const target = initial.saved.file_workers === 1 ? 2 : 1
  let restartIssued = false,
    restartObserved = false
  const read = async () => {
    const response = await request.get(path).catch(() => null)
    return response?.ok()
      ? zConfigState.parse(await response.json())
      : undefined
  }
  try {
    await openWorkbenchSettings(page)
    const panel = page.getByTestId('workbench-settings')
    const other = await context.newPage()
    await openWorkbenchSettings(other)
    const otherPanel = other.getByTestId('workbench-settings')
    await otherPanel.locator('#file_workers').fill(String(target + 2))
    await panel.locator('#file_workers').fill(String(target))
    await panel.getByRole('button', { name: '保存配置', exact: true }).click()
    await expect(panel.getByTestId('configuration-state')).toContainText(
      '需要重启'
    )
    const pending = (await read())!
    expect(pending.saved.file_workers).toBe(target)
    expect(pending.effective!.file_workers).toBe(
      initial.effective!.file_workers
    )
    const conflict = other.waitForResponse(
      (r) =>
        r.request().method() === 'PATCH' &&
        new URL(r.url()).pathname.endsWith('/settings/workbench')
    )
    await otherPanel
      .getByRole('button', { name: '保存配置', exact: true })
      .click()
    expect((await conflict).status()).toBe(409)
    await expect(otherPanel.getByRole('alert')).toBeVisible()
    await expect(otherPanel.locator('#file_workers')).toHaveValue(
      String(target + 2)
    )
    await other.close()
    await expect(panel.getByRole('link')).toHaveAttribute('href', baseURL!)
    await expect(panel.getByRole('link')).toHaveAttribute('target', '_blank')
    restartIssued = true
    await panel.getByTestId('workbench-restart').click()
    await expect
      .poll(async () => (await read())?.effective?.file_workers, {
        timeout: 120_000
      })
      .toBe(target)
    restartObserved = true
    await expect(panel.locator('#file_workers')).toHaveValue(String(target))
    await expect(panel.getByTestId('configuration-state')).toContainText(
      '配置已生效'
    )
  } finally {
    // A restart with an unknown result is observed before any cleanup write.
    if (restartIssued && !restartObserved) {
      await expect
        .poll(async () => (await read())?.effective?.file_workers, {
          timeout: 120_000
        })
        .toBe(target)
    }
    const current = await read()
    expect(current).toBeDefined()
    if (current!.saved.file_workers !== initial.saved.file_workers) {
      await openWorkbenchSettings(page)
      const panel = page.getByTestId('workbench-settings')
      await panel
        .locator('#file_workers')
        .fill(String(initial.saved.file_workers))
      await panel.getByRole('button', { name: '保存配置', exact: true }).click()
      await expect
        .poll(async () => (await read())?.saved.file_workers)
        .toBe(initial.saved.file_workers)
      if ((await read())!.restart_required) {
        await panel.getByTestId('workbench-restart').click()
        await expect
          .poll(async () => (await read())?.effective?.file_workers, {
            timeout: 120_000
          })
          .toBe(initial.effective!.file_workers)
      }
    }
    const restored = (await read())!
    expect(restored.saved.file_workers).toBe(initial.saved.file_workers)
    expect(restored.effective!.file_workers).toBe(
      initial.effective!.file_workers
    )
    expect(restored.restart_required).toBe(false)
    await test.info().attach('configuration-restored', {
      body: JSON.stringify({
        initial_saved: initial.saved.file_workers,
        initial_effective: initial.effective!.file_workers,
        adopted: target,
        restored_saved: restored.saved.file_workers,
        restored_effective: restored.effective!.file_workers
      }),
      contentType: 'application/json'
    })
  }
})

import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium, expect } from '../../frontend/node_modules/@playwright/test/index.mjs'

const base = process.env.APF_WEB_URL
assert.ok(base, 'Set APF_WEB_URL to the isolated preview instance')
const report = new URL('../../.artifacts/verification/m2-final-20261029/layout/', import.meta.url)
await mkdir(report, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE })
const checks = []
try {
  for (const width of [1280, 900]) {
    const page = await browser.newPage({ viewport: { width, height: 900 }, locale: 'zh-CN' })
    const errors = []
    page.on('pageerror', error => errors.push(String(error)))
    await page.goto(base)
    await expect(page.locator('#splash-loader')).toBeHidden({ timeout: 60000 })
    if (!await page.getByTestId('library-sidebar').isVisible()) await page.getByTestId('library-tab-button').click()
    const workspace = page.locator('.apf-workspace')
    await expect(workspace.getByRole('button', { name: '设备管理', exact: true })).toBeVisible()
    const library = await workspace.locator('.apf-main').boundingBox()
    await workspace.getByRole('button', { name: '设备管理', exact: true }).click()
    await expect(workspace.getByRole('heading', { name: '设备管理', exact: true })).toBeVisible()
    const equipment = await workspace.locator('.apf-main').boundingBox()
    assert.ok(library && equipment)
    assert.ok(Math.abs(library.x - equipment.x) <= 1)
    assert.ok(Math.abs(library.width - equipment.width) <= 1)
    for (const label of ['设备组合', '我的设备']) {
      const tab = workspace.getByRole('tab', { name: label, exact: true })
      await tab.click()
      await expect(tab).toHaveAttribute('data-state', 'active')
      const tabs = await workspace.locator('.apf-management-tabs').boundingBox()
      const first = await workspace.getByRole('tab', { name: '设备组合', exact: true }).boundingBox()
      assert.ok(tabs && first && Math.abs(tabs.x - first.x) <= 4, 'equipment tabs must be left aligned')
      await page.screenshot({ path: fileURLToPath(new URL(`${width}-${label}.png`, report)) })
    }
    assert.deepEqual(errors, [])
    checks.push({ width, library, equipment, errors })
    await page.close()
  }
  await writeFile(new URL('result.json', report), JSON.stringify(checks, null, 2))
} finally {
  await browser.close()
}

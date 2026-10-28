import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'

import { chromium, expect } from '../../frontend/node_modules/@playwright/test/index.mjs'

const base = process.env.APF_WEB_URL
const workspaceInput = process.env.APF_QA_WORKSPACE_A
assert.ok(base && workspaceInput, 'Set APF_WEB_URL and APF_QA_WORKSPACE_A for the isolated M1 instance')
const workspace = resolve(workspaceInput)
const workspaceRoot = fileURLToPath(new URL('../../.artifacts/workspaces/', import.meta.url))
assert.ok(!relative(workspaceRoot, workspace).startsWith('..'))
assert.notEqual(workspace, resolve(workspaceRoot, 'dev'))
let origin = new URL(base).origin
const report = fileURLToPath(new URL('../../.artifacts/implementation/B13/browser/', import.meta.url))
await mkdir(report, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'zh-CN', extraHTTPHeaders: { Origin: origin } })
const page = await context.newPage()
const errors = []
const checks = []
page.on('pageerror', error => errors.push(String(error)))
let configurationUrl = origin + '/astrophotoflow/api/v1/settings/workbench'
const run = promisify(execFile)
const python = process.env.APF_PYTHON ?? fileURLToPath(new URL('../../.artifacts/venvs/dev/Scripts/python.exe', import.meta.url))

async function openSettings(target) {
  await target.goto(origin, { waitUntil: 'domcontentloaded' })
  await expect(target.locator('#splash-loader')).toBeHidden({ timeout: 45000 })
  await expect(target.locator('#graph-canvas')).toBeVisible({ timeout: 45000 })
  await expect(target.getByTestId('workbench-settings-button')).toBeVisible({ timeout: 45000 })
  await target.getByTestId('workbench-settings-button').click()
  await expect(target.getByTestId('workbench-settings').locator('input[name="file_workers"]')).toBeVisible()
}

try {
  const first = await context.request.get(configurationUrl)
  assert.equal(first.status(), 200)
  const initial = await first.json()
  assert.equal(resolve(initial.config_path), join(workspace, 'config.toml'))
  assert.ok(initial.effective)
  const targetWorkers = Math.max(initial.effective.file_workers, initial.saved.file_workers) + 1
  const profile = await context.request.post(origin + '/api/settings', { data: { 'Comfy.TutorialCompleted': true, 'Comfy.Locale': 'zh' } })
  assert.equal(profile.status(), 200)
  await openSettings(page)
  await expect(page.locator('#graph-canvas')).toBeAttached()
  await page.screenshot({ path: join(report, 'configuration-initial.png'), fullPage: true })
  const other = await context.newPage()
  other.on('pageerror', error => errors.push(String(error)))
  await openSettings(other)
  await page.locator('input[name="file_workers"]').fill(String(targetWorkers))
  await page.getByRole('button', { name: '保存配置', exact: true }).click()
  await expect(page.getByTestId('configuration-state')).toContainText('需要重启')
  await expect(page.getByTestId('effective-file-workers')).toContainText(String(initial.effective.file_workers))
  const pending = await (await context.request.get(configurationUrl)).json()
  assert.equal(pending.saved.file_workers, targetWorkers)
  assert.equal(pending.effective.file_workers, initial.effective.file_workers)
  assert.ok(pending.restart_required)
  await page.screenshot({ path: join(report, 'configuration-pending.png'), fullPage: true })
  checks.push('real GUI save preserves running values and connection')
  await other.locator('input[name="file_workers"]').fill(String(targetWorkers + 1))
  await other.getByRole('button', { name: '保存配置', exact: true }).click()
  await expect(other.getByTestId('workbench-settings').getByRole('alert')).toContainText('配置已被修改')
  await expect(other.locator('input[name="file_workers"]')).toHaveValue(String(targetWorkers + 1))
  await other.screenshot({ path: join(report, 'configuration-conflict.png'), fullPage: true })
  await other.close()
  checks.push('stale page receives 409 and retains user input')
  const restarted = await run(python, ['-m', 'astrophotoflow.cli', 'restart', '--workspace', workspace], {
    env: { ...process.env, ASTROPHOTOFLOW_CONFIG: join(workspace, 'config.toml') }, timeout: 300000
  })
  const result = JSON.parse(restarted.stdout)
  assert.equal(result.state, 'completed')
  origin = new URL(result.web_url).origin
  configurationUrl = origin + '/astrophotoflow/api/v1/settings/workbench'
  await context.setExtraHTTPHeaders({ Origin: origin })
  await openSettings(page)
  await expect(page.getByTestId('effective-file-workers')).toContainText(String(targetWorkers))
  await expect(page.getByTestId('configuration-state')).toContainText('没有待重启')
  await page.screenshot({ path: join(report, 'configuration-after-restart.png'), fullPage: true })
  checks.push('real CLI restart adopts the saved settings and clears pending state')
  await page.locator('details summary').click()
  await page.locator('input[name="host"]').fill('0.0.0.0')
  await page.getByRole('button', { name: '保存配置', exact: true }).click()
  await expect(page.getByTestId('workbench-settings').getByRole('alert')).toContainText('本机回环地址')
  const afterInvalid = await (await context.request.get(configurationUrl, { headers: { Origin: origin } })).json()
  assert.equal(afterInvalid.saved.host, '127.0.0.1')
  await page.getByRole('button', { name: '重新读取最新值（替换未保存输入）', exact: true }).click()
  await expect(page.getByTestId('workbench-settings').getByRole('alert')).toHaveCount(0)
  checks.push('invalid host is rejected without changing the saved configuration')
  await page.getByRole('dialog', { name: '工作台配置', exact: true }).getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.locator('#graph-canvas')).toBeVisible()
  assert.deepEqual(errors, [])
  checks.push('configuration dialog closes while retaining the native canvas')
  await writeFile(join(report, 'report.json'), JSON.stringify({ passed: true, origin, workspace, checks, errors, targetWorkers, browserVersion: browser.version(), browserExecutable: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }, null, 2))
  console.log(JSON.stringify({ passed: true, checks, report }, null, 2))
} catch (error) {
  await page.screenshot({ path: join(report, 'failure.png'), fullPage: true }).catch(() => {})
  await writeFile(join(report, 'report.json'), JSON.stringify({ passed: false, origin, checks, errors, error: String(error) }, null, 2))
  throw error
} finally {
  await browser.close()
}

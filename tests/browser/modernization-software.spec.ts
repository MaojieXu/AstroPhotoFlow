import { test, expect } from '../../frontend/node_modules/@playwright/test/index.mjs'
import { readFile, writeFile } from 'node:fs/promises'
import { zPendingSoftwareAction, zSoftwarePackageDetails } from '../../frontend/packages/astrophotoflow-ui/src/generated/api/zod.gen'
import { reportRoot } from './modernization-paths.mjs'

test.skip(process.env.APF_ALLOW_SOFTWARE_INSTALL !== '1', 'Explicit opt-in required for the isolated software installation')

test('fixed Siril Bundle installs through the native confirmation page', async ({ page, request }) => {
  test.setTimeout(600_000)
  const health = await request.get('/astrophotoflow/api/v1/health')
  expect(health.ok()).toBe(true)
  expect((await health.json()).workspace.replaceAll('\\', '/').toLowerCase()).toContain('/.artifacts/workspaces/modernization-current')
  const initialResponse = await request.get('/astrophotoflow/api/v1/software/packages/siril')
  expect(initialResponse.ok()).toBe(true)
  const initial = zSoftwarePackageDetails.parse(await initialResponse.json())
  const verifyKnownFailedLoad = process.env.APF_VERIFY_INSTALLED_REPAIR === '1'
  if (verifyKnownFailedLoad) {
    const previous = JSON.parse(await readFile(new URL('native-software-install-failed.json', reportRoot), 'utf8'))
    expect(previous.details.current_action.state).toBe('failed')
    expect(previous.details.current_action.error.code).toBe('BUNDLE_LOAD_FAILED')
    expect(initial.package.installed_version).toBe('1.4.4')
  }
  test.skip(initial.package.installed_version !== null && !verifyKnownFailedLoad, 'Already installed; preserve the earlier installation evidence instead of reinstalling')
  expect(['running', 'unknown']).not.toContain(initial.current_action?.state)
  let pending = initial.current_action?.state === 'awaiting_confirmation' ? initial.current_action : undefined
  if (!pending) {
    const response = await request.post('/astrophotoflow/api/v1/software/packages/siril/install', {
      data: { version: '1.4.4', package_token: initial.package.package_token },
    })
    expect(response.status()).toBe(202)
    pending = zPendingSoftwareAction.parse(await response.json())
  }
  expect(pending.state).toBe('awaiting_confirmation')
  expect(pending.plan.target_version).toBe('1.4.4')
  expect(pending.plan.source).toContain('v0.2.0-dev.2')
  expect(pending.plan.source).toContain('5d16fb6fc10b4ee57de428d6eba522c918b1b441')
  const evidence = new URL('native-software-install.json', reportRoot)
  await writeFile(evidence, JSON.stringify({ pending }, null, 2))
  await page.goto(pending.confirmation_url)
  await page.waitForFunction(() => window.app?.api.socket?.readyState === WebSocket.OPEN)
  const confirm = page.getByRole('dialog').getByTestId('confirm-software')
  await expect(confirm).toBeEnabled()
  await confirm.click()
  let details = initial
  let previous: string | undefined
  await expect.poll(async () => {
    const response = await request.get(`/astrophotoflow/api/v1/software/packages/siril?operation_id=${pending.operation_id}`)
    expect(response.ok()).toBe(true)
    details = zSoftwarePackageDetails.parse(await response.json())
    await writeFile(evidence, JSON.stringify({ pending, details }, null, 2))
    const state = details.current_action?.state
    const phase = `${state}:${details.package.phase}:${details.package.progress}`
    if (phase !== previous) { console.log(phase); previous = phase }
    return state
  }, { timeout: 480_000, intervals: [1_000, 2_000, 5_000] }).toMatch(/^(completed|failed|expired|unknown)$/)
  expect(details.current_action?.state, JSON.stringify(details.current_action?.error)).toBe('completed')
  expect(details.package.installed_version).toBe('1.4.4')
  await expect.poll(async () => {
    const response = await request.get('/object_info')
    expect(response.ok()).toBe(true)
    return Object.keys(await response.json()).filter(key => /^APF_[a-f0-9]{32}$/.test(key)).length
  }).toBe(160)
})

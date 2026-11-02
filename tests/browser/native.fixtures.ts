import {
  test as base,
  expect
} from '../../frontend/node_modules/@playwright/test/index.mjs'
import type { Page } from '../../frontend/node_modules/@playwright/test/index.mjs'
import { resolve, relative, isAbsolute } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  zServiceHealth,
  zConfigState
} from '../../frontend/packages/astrophotoflow-ui/src/generated/api/zod.gen'

export const test = base.extend<{
  isolatedWorkspace: string
  browserErrors: string[]
}>({
  isolatedWorkspace: [
    async ({ request, baseURL }, use) => {
      if (!baseURL || !process.env.APF_TEST_WORKSPACE)
        throw new Error(
          'Set APF_WEB_URL and APF_TEST_WORKSPACE to the prepared isolated Feature preview'
        )
      const root = fileURLToPath(
        new URL('../../.artifacts/workspaces/', import.meta.url)
      )
      const selected = resolve(process.env.APF_TEST_WORKSPACE)
      const child = relative(root, selected)
      expect(
        child && !child.startsWith('..') && !isAbsolute(child),
        'Test workspace must be inside this worktree .artifacts/workspaces'
      ).toBeTruthy()
      expect(
        ['dev', 'default'],
        'Shared/default workspaces are protected'
      ).not.toContain(child.toLowerCase())
      const health = await request.get('/astrophotoflow/api/v1/health')
      expect(health.status()).toBe(200)
      expect(
        resolve(
          zServiceHealth.parse(await health.json()).workspace
        ).toLowerCase()
      ).toBe(selected.toLowerCase())
      const config = await request.get(
        '/astrophotoflow/api/v1/settings/workbench'
      )
      expect(config.status()).toBe(200)
      const configuration = zConfigState.parse(await config.json())
      expect(resolve(configuration.config_path).toLowerCase()).toBe(
        resolve(selected, 'config.toml').toLowerCase()
      )
      const dataChild = relative(
        selected,
        resolve(configuration.data_dir_absolute)
      )
      expect(
        dataChild && !dataChild.startsWith('..') && !isAbsolute(dataChild),
        'Test data must stay inside the selected private workspace'
      ).toBeTruthy()
      const profile = await request.post('/api/settings', {
        data: { 'Comfy.TutorialCompleted': true, 'Comfy.Locale': 'zh' }
      })
      expect(profile.status()).toBe(200)
      await use(selected)
    },
    { auto: true }
  ],
  browserErrors: [
    async ({ page, context, baseURL }, use) => {
      const errors: string[] = [],
        remote: string[] = []
      page.on('pageerror', (error) => errors.push(String(error)))
      await context.route('**/*', (route) => {
        const url = new URL(route.request().url())
        if (
          ['http:', 'https:'].includes(url.protocol) &&
          url.origin !== new URL(baseURL!).origin
        ) {
          remote.push(url.origin)
          return route.abort()
        }
        return route.continue()
      })
      await use(errors)
      expect(errors).toEqual([])
      expect(remote).toEqual([])
    },
    { auto: true }
  ]
})
export { expect }

export async function openWorkbenchSettings(page: Page) {
  await page.goto('/')
  await expect(page.locator('#graph-canvas')).toBeVisible({ timeout: 45_000 })
  await page
    .getByRole('button', { name: '设置 (Ctrl + ,)', exact: true })
    .click()
  await page.getByText('工作台', { exact: true }).first().click()
  await expect(page.getByTestId('workbench-settings')).toBeVisible()
}

export async function openSidebar(
  page: Page,
  id: 'library' | 'projects' | 'node-library' | 'workflows'
) {
  await page.getByTestId(id + '-tab-button').click()
  if (id !== 'node-library')
    await expect(page.getByTestId(id + '-sidebar')).toBeVisible()
}

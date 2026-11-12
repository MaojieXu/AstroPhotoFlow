import { defineConfig } from '../../frontend/node_modules/@playwright/test/index.mjs'
import { fileURLToPath } from 'node:url'
import { resolve, relative, isAbsolute } from 'node:path'

const baseURL = process.env.APF_WEB_URL
if (
  baseURL &&
  !['127.0.0.1', 'localhost', '[::1]'].includes(new URL(baseURL).hostname)
) {
  throw new Error(
    'Browser validation requires an explicitly selected local workspace'
  )
}
const reportParent = fileURLToPath(
  new URL('../../.artifacts/reports/', import.meta.url)
)
const reports = resolve(
  process.env.APF_BROWSER_REPORT ?? resolve(reportParent, 'browser')
)
const reportChild = relative(reportParent, reports)
if (!reportChild || reportChild.startsWith('..') || isAbsolute(reportChild)) {
  throw new Error(
    'Browser reports must stay in a dedicated worktree .artifacts/reports subdirectory'
  )
}
export default defineConfig({
  testDir: '.',
  testMatch: [
    'node-ui.spec.ts',
    'node-localizations.spec.ts',
    'bundle-hot-reload.spec.ts',
    'native-web.spec.ts',
    'native-layout.spec.ts',
    'workbench-settings.spec.ts'
  ],
  workers: 1,
  retries: 0,
  forbidOnly: true,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  outputDir: reports + '/results',
  reporter: [
    ['list'],
    ['junit', { outputFile: reports + '/results.xml' }],
    ['json', { outputFile: reports + '/results.json' }]
  ],
  use: {
    baseURL,
    browserName: 'chromium',
    headless: true,
    viewport: { width: 1440, height: 1000 },
    locale: 'zh-CN',
    extraHTTPHeaders: baseURL ? { Origin: new URL(baseURL).origin } : {},
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
    },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  }
})

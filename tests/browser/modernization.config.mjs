import { defineConfig } from '../../frontend/node_modules/@playwright/test/index.mjs';
import { fileURLToPath } from 'node:url';
import { reportRoot } from './modernization-paths.mjs';
const baseURL = process.env.APF_WEB_URL;
if (baseURL !== 'http://127.0.0.1:32588') throw new Error('This fixture targets only the explicitly prepared modernization-preview workspace');
const report = fileURLToPath(reportRoot);
export default defineConfig({
  testDir: '.', testMatch: 'modernization-library.spec.ts', workers: 1, retries: 0, forbidOnly: true,
  timeout: 60000, expect: {timeout: 15000}, outputDir: report + '/browser-results-indexed',
  reporter: [['list'], ['junit', {outputFile: report + '/browser-library-indexed.xml'}], ['json', {outputFile: report + '/browser-library-indexed.json'}]],
  use: {baseURL, browserName: 'chromium', headless: true, viewport: {width: 1440, height: 1000}, locale: 'zh-CN',
    extraHTTPHeaders: {Origin: baseURL}, trace: 'retain-on-failure', screenshot: 'only-on-failure'},
});

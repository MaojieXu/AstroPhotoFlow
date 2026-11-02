import { defineConfig } from '../../frontend/node_modules/@playwright/test/index.mjs'
import { fileURLToPath } from 'node:url'
import base from './modernization.config.mjs'
import { reportRoot } from './modernization-paths.mjs'

const report = fileURLToPath(reportRoot)
export default defineConfig({
  ...base,
  testMatch: ['modernization-native.spec.ts', 'modernization-software.spec.ts', 'modernization-science.spec.ts', 'modernization-canvas.spec.ts', 'modernization-automatic.spec.ts'],
  outputDir: report + '/browser-native-results',
  reporter: [
    ['list'],
    ['junit', { outputFile: report + '/browser-native.xml' }],
    ['json', { outputFile: report + '/browser-native.json' }],
  ],
})

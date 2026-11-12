import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { mkdir, realpath, writeFile } from 'node:fs/promises'
import path from 'node:path'

const root = fileURLToPath(new URL('../', import.meta.url))
const require = createRequire(await realpath(path.join(root, 'frontend/node_modules/tsx/package.json')))
const { build } = require('esbuild')
const output = path.join(root, '.artifacts/reports/modernization/g0')
await mkdir(output, { recursive: true })
await build({
  entryPoints: [path.join(root, 'scripts/modernization/verify_generated.ts')],
  outfile: path.join(output, 'verify-generated.mjs'),
  bundle: true,
  platform: 'node',
  format: 'esm',
  nodePaths: [path.join(root, 'frontend/packages/astrophotoflow-ui/node_modules'), path.join(root, 'frontend/node_modules')],
})
await import(new URL('../.artifacts/reports/modernization/g0/verify-generated.mjs', import.meta.url))
await writeFile(path.join(output, 'tsconfig.json'), JSON.stringify({
  compilerOptions: {
    target: 'ES2022', module: 'ESNext', moduleResolution: 'Bundler', strict: true, noEmit: true, skipLibCheck: true,
    lib: ['ES2022', 'DOM', 'DOM.Iterable'],
    paths: {
      zod: [path.join(root, 'frontend/node_modules/zod')],
      '@tanstack/vue-query': [path.join(root, 'frontend/packages/astrophotoflow-ui/node_modules/@tanstack/vue-query')],
      '@hey-api/openapi-ts': [path.join(root, 'frontend/packages/astrophotoflow-ui/node_modules/@hey-api/openapi-ts')],
      'node:*': [path.join(root, 'frontend/node_modules/@types/node/*')],
    },
  },
  include: [path.join(output, 'generated/**/*.ts'), path.join(root, 'scripts/modernization/verify_generated.ts'),
    path.join(root, 'frontend/packages/astrophotoflow-ui/openapi-ts.config.ts')],
}, null, 2))
await writeFile(path.join(output, 'sdk.json'), JSON.stringify({
  passed: true,
  checks: ['required nullable', 'optional nullable', 'zero', 'discriminated union', 'UTC date', 'offset date',
    'array query encoding', 'binary Blob', 'error envelope', 'response validation', 'Vue Query options'],
}, null, 2))

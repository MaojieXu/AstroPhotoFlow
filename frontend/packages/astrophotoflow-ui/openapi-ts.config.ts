import { defineConfig } from '@hey-api/openapi-ts'
import { fileURLToPath } from 'node:url'
import { readFileSync } from 'node:fs'
import { normalizeEnumMaps, normalizeJsonValue } from './openapi-input'

const root = new URL('../../../', import.meta.url)
const inputPath =
  process.env.APF_OPENAPI_INPUT ??
  fileURLToPath(new URL('docs/api/openapi.json', root))
const rawDocument: unknown = JSON.parse(readFileSync(inputPath, 'utf8'))
if (
  typeof rawDocument !== 'object' ||
  rawDocument === null ||
  Array.isArray(rawDocument)
)
  throw new Error('OpenAPI input must be a document object.')
const document: Record<string, unknown> = { ...rawDocument }

// G0 sets explicit input/output paths for its isolated fixture. G3 uses the
// same pipeline for the complete platform contract.
export default defineConfig({
  input: normalizeJsonValue(normalizeEnumMaps(document)),
  output:
    process.env.APF_SDK_OUTPUT ??
    fileURLToPath(
      new URL('frontend/packages/astrophotoflow-ui/src/generated/api', root)
    ),
  plugins: [
    '@hey-api/typescript',
    '@hey-api/client-fetch',
    {
      name: 'zod',
      compatibilityVersion: 4,
      dates: { offset: true },
      // 0.99.0 otherwise emits z.string() for binary, while its Fetch SDK
      // correctly returns Blob. Keep the correction in the generator.
      $resolvers: {
        // The normalized IR represents additionalProperties:false as never.
        object: (ctx) =>
          typeof ctx.schema.additionalProperties === 'object' &&
          ctx.schema.additionalProperties.type === 'never'
            ? ctx.nodes.base(ctx).attr('strict').call()
            : undefined,
        string: (ctx) =>
          ctx.schema.format === 'binary'
            ? ctx.$(ctx.plugin.imports.z).attr('instanceof').call(ctx.$('Blob'))
            : undefined
      }
    },
    { name: '@hey-api/sdk', validator: true },
    '@tanstack/vue-query'
  ]
})

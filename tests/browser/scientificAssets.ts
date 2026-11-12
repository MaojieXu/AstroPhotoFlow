import type { APIRequestContext } from '../../frontend/node_modules/@playwright/test/index.mjs'
import { expect } from '../../frontend/node_modules/@playwright/test/index.mjs'
import {
  zAssetOut,
  zAssetTaskOut,
  zImportAccepted,
  zUploadImportCreate,
  zUploadReceipt
} from '../../frontend/packages/astrophotoflow-ui/src/generated/api/zod.gen'

/** Every scenario owns its input: no existing library member is repurposed. */
export async function createSyntheticAsset(
  request: APIRequestContext,
  name: string,
  phase = 0,
  channels: 1 | 3 = 1
) {
  const size = 128
  const cards = [
    'SIMPLE  =                    T',
    'BITPIX  =                  -32',
    `NAXIS   =                    ${channels === 1 ? 2 : 3}`,
    'NAXIS1  =                  128',
    'NAXIS2  =                  128',
    ...(channels === 3 ? ['NAXIS3  =                    3', "CTYPE3  = 'RGB'"] : []),
    'END'
  ]
  const header = Buffer.from(
    cards
      .map((card) => card.padEnd(80))
      .join('')
      .padEnd(2880),
    'ascii'
  )
  const pixels = Buffer.alloc(Math.ceil((size * size * 4 * channels) / 2880) * 2880)
  for (let channel = 0; channel < channels; channel++) {
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      pixels.writeFloatBE(
        0.1 + channel * 0.05 + x / 256 + y / 512 + 0.02 * Math.sin((x + y + phase) / 5),
        (channel * size * size + y * size + x) * 4
      )
    }
  }
  }
  const bytes = Buffer.concat([header, pixels])
  return uploadAssetBytes(request, name + '.fits', bytes)
}

export async function uploadAssetBytes(
  request: APIRequestContext,
  filename: string,
  bytes: Buffer
) {
  const submitted = await request.post('/astrophotoflow/api/v1/uploads', {
    data: zUploadImportCreate.parse({
      files: [{ name: filename, size: bytes.length }]
    })
  })
  expect(submitted.status()).toBe(202)
  const accepted = zImportAccepted.parse(await submitted.json())
  const uploaded = await request.put(
    `/astrophotoflow/api/v1/uploads/${accepted.task_id}/0`,
    {
      headers: { 'Content-Type': 'application/octet-stream' },
      data: bytes
    }
  )
  expect(uploaded.status()).toBe(200)
  zUploadReceipt.parse(await uploaded.json())
  const started = await request.post(
    `/astrophotoflow/api/v1/uploads/${accepted.task_id}/start`
  )
  expect(started.status()).toBe(202)
  zImportAccepted.parse(await started.json())
  let task: ReturnType<typeof zAssetTaskOut.parse> | undefined
  await expect
    .poll(async () => {
      const response = await request.get(
        `/astrophotoflow/api/v1/asset-tasks/${accepted.task_id}`
      )
      expect(response.status()).toBe(200)
      task = zAssetTaskOut.parse(await response.json())
      return [
        'completed',
        'completed_with_errors',
        'failed',
        'cancelled'
      ].includes(task.status)
    })
    .toBe(true)
  expect(task!.status).toBe('completed')
  expect(task!.items).toHaveLength(1)
  const response = await request.get(
    '/astrophotoflow/api/v1/library/assets/' + task!.items[0].asset_id
  )
  expect(response.status()).toBe(200)
  return zAssetOut.parse(await response.json())
}

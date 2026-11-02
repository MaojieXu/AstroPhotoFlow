import { expect, it, vi } from 'vitest'
import { validatedInput } from '@ui/core/api/input'
import { createMutationClient } from '@ui/modules/data/api/mutations'
import {
  zPatchAssetApiV1LibraryAssetsAssetIdPatchBody,
  zCreateProjectApiV1ProjectsPostBody
} from '@ui/generated/api/zod.gen'

const id = '00000000-0000-4000-8000-000000000001'

it('validates sparse inputs without inserting defaults or losing null and zero', () => {
  const patch = { base_revision: 4, parameters: { gain: 0, offset: null } }
  expect(
    validatedInput(zPatchAssetApiV1LibraryAssetsAssetIdPatchBody, patch)
  ).toBe(patch)
  const create = { name: 'M31' }
  expect(validatedInput(zCreateProjectApiV1ProjectsPostBody, create)).toBe(
    create
  )
  expect(Object.keys(create)).toEqual(['name'])
})

it('rejects invalid form data before making a request', () => {
  expect(() =>
    validatedInput(zPatchAssetApiV1LibraryAssetsAssetIdPatchBody, {
      base_revision: 1,
      parameters: { gain: 'invalid' }
    })
  ).toThrow(
    expect.objectContaining({ kind: 'contract', code: 'INVALID_REQUEST' })
  )
})

it('does not replay an uncertain write or replace its revision', async () => {
  const fetch = vi.fn().mockRejectedValue(new TypeError('reply lost'))
  const client = createMutationClient(fetch)
  await expect(
    client.patchAsset(id, {
      base_revision: 4,
      parameters: { gain: 0, offset: null }
    })
  ).rejects.toMatchObject({ kind: 'network' })
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
    base_revision: 4,
    parameters: { gain: 0, offset: null }
  })
})

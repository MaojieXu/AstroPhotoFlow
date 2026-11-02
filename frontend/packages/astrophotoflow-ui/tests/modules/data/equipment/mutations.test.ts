import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import type { QueryClient } from '@tanstack/vue-query'
import { afterEach, expect, it, vi } from 'vitest'
import { workspaceQueryKey } from '@ui/core/query/keys'
import {
  useSaveSetup,
  useSavePreset,
  useCreateEquipment
} from '@ui/modules/data/equipment/mutations'

const { createEquipment, createSetup, patchSetup, createPreset, patchPreset } =
  vi.hoisted(() => ({
    createEquipment: vi.fn(),
    createSetup: vi.fn(),
    patchSetup: vi.fn(),
    createPreset: vi.fn(),
    patchPreset: vi.fn()
  }))
vi.mock('@ui/modules/data/api/index', () => ({
  mutationApi: {
    createEquipment,
    createSetup,
    patchSetup,
    createPreset,
    patchPreset
  }
}))
let wrapper: ReturnType<typeof mount> | undefined
const id = '00000000-0000-4000-8000-000000000001'
afterEach(() => {
  wrapper?.unmount()
  vi.resetAllMocks()
})
function setup<T>(build: () => T) {
  let owner!: T, cache!: QueryClient
  wrapper = mount(
    defineComponent({
      setup() {
        owner = build()
        cache = useQueryClient()
        return () => null
      }
    })
  )
  for (const workspace of ['/one', '/two'])
    for (const part of [
      ['equipment'],
      ['equipment', 'presets', id],
      ['equipment', 'import-presets'],
      ['trash'],
      ['library']
    ])
      cache.setQueryData([...workspaceQueryKey(workspace), ...part], {
        workspace
      })
  return { owner, cache }
}

it('saves a setup with its reviewed revision and invalidates only original equipment resources', async () => {
  const { owner, cache } = setup(useSaveSetup)
  patchSetup.mockResolvedValue({ id, revision: 5 })
  const body = {
    name: 'Fixed setup',
    base_revision: 4,
    components: [{ source: 'registered' as const, equipment_id: id }]
  }
  await owner.mutateAsync({
    workspaceId: '/one',
    action: 'update',
    setupId: id,
    body
  })
  expect(patchSetup).toHaveBeenCalledExactlyOnceWith(id, body)
  expect(createSetup).not.toHaveBeenCalled()
  expect(
    cache.getQueryState([
      ...workspaceQueryKey('/one'),
      'equipment',
      'presets',
      id
    ])?.isInvalidated
  ).toBe(true)
  expect(
    cache.getQueryState([
      ...workspaceQueryKey('/one'),
      'equipment',
      'import-presets'
    ])?.isInvalidated
  ).toBe(true)
  expect(
    cache.getQueryState([...workspaceQueryKey('/two'), 'equipment'])
      ?.isInvalidated
  ).toBe(false)
  expect(
    cache.getQueryState([...workspaceQueryKey('/one'), 'library'])
      ?.isInvalidated
  ).toBe(false)
})

it('preserves sparse preset selections, zero and explicit null through a create request', async () => {
  const { owner } = setup(useSavePreset)
  createPreset.mockResolvedValue({ id })
  const body = {
    equipment_selection: { filter: null },
    parameters: { gain: 0, offset: null }
  }
  await owner.mutateAsync({
    workspaceId: '/one',
    action: 'create',
    setupId: id,
    body
  })
  expect(createPreset).toHaveBeenCalledExactlyOnceWith(id, body)
  expect(patchPreset).not.toHaveBeenCalled()
  expect(body.equipment_selection).not.toHaveProperty('camera')
})

it('invalidates a failed original preset write without retrying the unknown outcome', async () => {
  const { owner, cache } = setup(useSavePreset)
  patchPreset.mockRejectedValue(new Error('Outcome unknown'))
  await expect(
    owner.mutateAsync({
      workspaceId: '/one',
      action: 'update',
      presetId: id,
      body: { base_revision: 8, parameters: { offset: null } }
    })
  ).rejects.toThrow('Outcome unknown')
  expect(patchPreset).toHaveBeenCalledTimes(1)
  expect(
    cache.getQueryState([
      ...workspaceQueryKey('/one'),
      'equipment',
      'import-presets'
    ])?.isInvalidated
  ).toBe(true)
  expect(
    cache.getQueryState([
      ...workspaceQueryKey('/two'),
      'equipment',
      'import-presets'
    ])?.isInvalidated
  ).toBe(false)
})

it('publishes device facts independently of cancelling the local setup draft', async () => {
  const { owner, cache } = setup(useCreateEquipment)
  createEquipment.mockResolvedValue({
    id,
    kind: 'camera',
    name: 'Saved camera'
  })
  await owner.mutateAsync({
    workspaceId: '/one',
    body: {
      kind: 'camera',
      name: 'Saved camera',
      specs: { pixel_size_um: 3.76 }
    }
  })
  expect(createEquipment).toHaveBeenCalledTimes(1)
  expect(
    cache.getQueryState([...workspaceQueryKey('/one'), 'equipment'])
      ?.isInvalidated
  ).toBe(true)
  expect(createSetup).not.toHaveBeenCalled()
})

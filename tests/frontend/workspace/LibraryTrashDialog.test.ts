import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, it, expect, vi } from 'vitest'
import LibraryTrashDialog from '@frontend/workspace/LibraryTrashDialog.vue'

const { get, send } = vi.hoisted(() => ({ get: vi.fn(), send: vi.fn() }))
vi.mock('@frontend/assets/host-client', () => ({ assetApi: { get, send } }))
const id = (n: number) => '00000000-0000-4000-8000-' + String(n).padStart(12, '0')
const item = (entry_type: string, n: number, name: string) => ({ entry_type, id: id(n), name,
  removed_at: '2026-10-24T12:00:00Z', revision: 1, current_version_id: null, cleanup_status: 'trash',
  cleanup_error: null, photo_count: 1, member_asset_ids: [], groups: [], source_dataset_id: null })
const page = (items: unknown[], total = items.length, offset = 0) => ({ items, total, limit: 20, offset })
beforeEach(() => { get.mockReset(); send.mockReset() })

it('places expanded photos immediately below their parent group', async () => {
  const groups = [{ ...item('dataset', 11, 'Group one'), member_asset_ids: [id(1)] },
    { ...item('dataset', 12, 'Group two'), member_asset_ids: [id(2)] }]
  get.mockImplementation(async (path: string) => path.includes('group_id=')
    ? page([{ ...item('asset', 1, 'A.fit'), source_dataset_id: id(11) }])
    : page(groups))
  const wrapper = mount(LibraryTrashDialog, { props: { open: true } })
  try {
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '展开')!.trigger('click')
    await flushPromises()
    const names = wrapper.findAll('tbody tr').filter(row => row.findAll('td').length === 5)
      .map(row => row.findAll('td')[1].text())
    expect(names[0]).toContain('Group one')
    expect(names[1]).toBe('A.fit')
    expect(names[2]).toContain('Group two')
  } finally { wrapper.unmount() }
})

it('removes the old page groups while the next top-level page is loading', async () => {
  const group = { ...item('dataset', 11, 'Old page group'), member_asset_ids: [id(1)] }
  let finishNext!: (value: unknown) => void
  get.mockImplementation((path: string) => {
    const query = new URL(path, 'http://local.test').searchParams
    if (query.has('group_id')) return Promise.resolve(page([{ ...item('asset', 1, 'Old group child'), source_dataset_id: id(11) }]))
    if (query.get('offset') === '20') return new Promise(resolve => { finishNext = resolve })
    return Promise.resolve(page([group], 21))
  })
  const wrapper = mount(LibraryTrashDialog, { props: { open: true } })
  try {
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '下一页')!.trigger('click')
    expect(wrapper.text()).toContain('正在读取垃圾桶')
    expect(wrapper.text()).not.toContain('Old page group')
    expect(wrapper.findAll('button').some(button => button.text() === '展开')).toBe(false)
    finishNext(page([item('asset', 2, 'Expected page two')], 21, 20)); await flushPromises()
    expect(wrapper.text()).toContain('Expected page two')
    expect(wrapper.text()).not.toContain('Old group child')
    expect(wrapper.text()).toContain('21–21 / 21')
    expect(get.mock.calls.some(([path]) => path.includes('group_id='))).toBe(false)
  } finally { wrapper.unmount() }
})

it('keeps the displayed and submitted child in the currently expanded group', async () => {
  const a = { ...item('asset', 1, 'A.fit'), source_dataset_id: id(11) }
  const b = { ...item('asset', 2, 'B.fit'), source_dataset_id: id(12) }
  const groups = [{ ...item('dataset', 11, 'Group one'), member_asset_ids: [id(1)] },
    { ...item('dataset', 12, 'Group two'), member_asset_ids: [id(2)] }]
  let resolveA!: (value: unknown) => void
  let resolveB!: (value: unknown) => void
  get.mockImplementation((path: string) => {
    const group = new URL(path, 'http://local.test').searchParams.get('group_id')
    if (group === id(11)) return new Promise(resolve => { resolveA = resolve })
    if (group === id(12)) return new Promise(resolve => { resolveB = resolve })
    return Promise.resolve(page(groups))
  })
  send.mockResolvedValue({ items: [], tasks: [], references: [], managed_bytes: 0,
    managed_file_count: 0, photo_count: 1, preview_fingerprint: 'review' })
  const wrapper = mount(LibraryTrashDialog, { props: { open: true } })
  try {
    await flushPromises()
    const expand = wrapper.findAll('button').filter(button => button.text() === '展开')
    await expand[0].trigger('click')
    await expand[1].trigger('click')
    resolveB(page([b])); await flushPromises()
    resolveA(page([a])); await flushPromises()
    expect(expand[1].attributes('aria-expanded')).toBe('true')
    await wrapper.get('.trash-child-row input[type="checkbox"]').setValue(true)
    await wrapper.findAll('button').find(button => button.text() === '永久删除')!.trigger('click')
    await flushPromises()
    expect(send.mock.calls[0][3].items[0].source_dataset_id).toBe(id(12))
  } finally { wrapper.unmount() }
})

it.each(['success', 'failure'])('ignores a child %s after close while the reopened list is loading', async outcome => {
  const group = { ...item('dataset', 11, 'Group'), member_asset_ids: [id(1)] }
  let finishChild!: (value: unknown) => void
  let failChild!: (error: Error) => void
  let finishList!: (value: unknown) => void
  let listCalls = 0
  get.mockImplementation((path: string) => {
    if (path.includes('group_id=')) return new Promise((resolve, reject) => { finishChild = resolve; failChild = reject })
    listCalls++
    return listCalls === 1 ? Promise.resolve(page([group])) : new Promise(resolve => { finishList = resolve })
  })
  const wrapper = mount(LibraryTrashDialog, { props: { open: true } })
  try {
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '展开')!.trigger('click')
    await wrapper.setProps({ open: false })
    await wrapper.setProps({ open: true })
    if (outcome === 'success') finishChild(page([{ ...item('asset', 1, 'Stale.fit'), source_dataset_id: id(11) }]))
    else failChild(new Error('stale group failure'))
    await flushPromises()
    expect(wrapper.text()).toContain('正在读取垃圾桶')
    expect(wrapper.text()).not.toContain('Stale.fit')
    expect(wrapper.text()).not.toContain('stale group failure')
    finishList(page([])); await flushPromises()
    expect(wrapper.text()).toContain('垃圾桶为空')
  } finally { wrapper.unmount() }
})

it('clears child selection and confirmation when paging within the same group', async () => {
  const group = { ...item('dataset', 11, 'Group'), member_asset_ids: [id(1), id(2)] }
  get.mockImplementation(async (path: string) => {
    if (!path.includes('group_id=')) return page([group])
    const second = new URL(path, 'http://local.test').searchParams.get('offset') === '20'
    return { ...page([{ ...item('asset', second ? 2 : 1, second ? 'B.fit' : 'A.fit'), source_dataset_id: id(11) }]), total: 21 }
  })
  send.mockResolvedValue({ items: [], tasks: [], references: [], managed_bytes: 0,
    managed_file_count: 0, photo_count: 1, preview_fingerprint: 'review' })
  const wrapper = mount(LibraryTrashDialog, { props: { open: true } })
  try {
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '展开')!.trigger('click'); await flushPromises()
    await wrapper.get('.trash-child-row input').setValue(true)
    await wrapper.findAll('button').find(button => button.text() === '永久删除')!.trigger('click'); await flushPromises()
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
    await wrapper.findAll('button').find(button => button.text() === '取消')!.trigger('click')
    await wrapper.findAll('button').find(button => button.text() === '组内下一页')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('B.fit')
    expect(wrapper.text()).not.toContain('A.fit')
    expect(wrapper.find('.trash-preview').exists()).toBe(false)
    expect(wrapper.findAll('button').find(button => button.text() === '恢复')!.attributes('disabled')).toBeDefined()
  } finally { wrapper.unmount() }
})

it('invalidates the preview and confirmation when the selection changes', async () => {
  get.mockResolvedValue(page([item('asset', 1, 'A.fit'), item('asset', 2, 'B.fit')]))
  send.mockResolvedValue({ items: [], tasks: [], references: [], managed_bytes: 0,
    managed_file_count: 0, photo_count: 1, preview_fingerprint: 'review' })
  const wrapper = mount(LibraryTrashDialog, { props: { open: true } })
  try {
    await flushPromises()
    await wrapper.get('input[aria-label="选择 A.fit"]').setValue(true)
    await wrapper.findAll('button').find(button => button.text() === '永久删除')!.trigger('click'); await flushPromises()
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
    await wrapper.get('input[aria-label="选择 B.fit"]').setValue(true)
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    expect(wrapper.find('.trash-preview').exists()).toBe(false)
    expect(send).toHaveBeenCalledTimes(1)
  } finally { wrapper.unmount() }
})

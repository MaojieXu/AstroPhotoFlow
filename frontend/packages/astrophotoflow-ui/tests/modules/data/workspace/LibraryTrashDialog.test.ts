import { mount, flushPromises } from '@vue/test-utils'
import { focusManager, useQueryClient } from '@tanstack/vue-query'
import { defineComponent, h } from 'vue'
import { trashQueryKey } from '@ui/modules/data/trash/queries'
import { ApiClientError } from '@ui/modules/data/api/client'
import { beforeEach, it, expect, vi } from 'vitest'
import LibraryTrashDialog from '@ui/modules/data/trash/LibraryTrashDialog.vue'

const { get, send } = vi.hoisted(() => ({ get: vi.fn(), send: vi.fn() }))
vi.mock('@ui/modules/data/api/index', async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send), assetApi: { get, send } }))
const id = (n: number) => '00000000-0000-4000-8000-' + String(n).padStart(12, '0')
const item = (entry_type: string, n: number, name: string) => ({ entry_type, id: id(n), name,
  removed_at: '2026-10-24T12:00:00Z', revision: 1, cleanup_status: 'trash',
  cleanup_error: null, photo_count: 1, member_asset_ids: [], groups: [], source_dataset_id: null })
const page = (items: unknown[], total = items.length, offset = 0) => ({ items, total, limit: 20, offset })
beforeEach(() => { get.mockReset(); send.mockReset() })

it('places expanded photos immediately below their parent group', async () => {
  const groups = [{ ...item('dataset', 11, 'Group one'), member_asset_ids: [id(1)] },
    { ...item('dataset', 12, 'Group two'), member_asset_ids: [id(2)] }]
  get.mockImplementation(async (path: string) => path.includes('group_id=')
    ? page([{ ...item('asset', 1, 'A.fit'), source_dataset_id: id(11) }])
    : page(groups))
  const wrapper = mount(LibraryTrashDialog, { props: { open: true, workspaceId:'trash-test-workspace' } })
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
  const wrapper = mount(LibraryTrashDialog, { props: { open: true, workspaceId:'trash-test-workspace' } })
  try {
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '下一页')!.trigger('click')
    expect(wrapper.text()).toContain('正在读取回收站')
    expect(wrapper.text()).not.toContain('Old page group')
    expect(wrapper.findAll('button').some(button => button.text() === '展开')).toBe(false)
    await flushPromises()
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
  const wrapper = mount(LibraryTrashDialog, { props: { open: true, workspaceId:'trash-test-workspace' } })
  try {
    await flushPromises()
    const expand = wrapper.findAll('button').filter(button => button.text() === '展开')
    await expand[0].trigger('click'); await flushPromises()
    await expand[1].trigger('click')
    await flushPromises()
    expect((get.mock.calls.find(([path])=>path.includes('group_id='+id(11)))![2] as AbortSignal).aborted).toBe(true)
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
  const wrapper = mount(LibraryTrashDialog, { props: { open: true, workspaceId:'trash-test-workspace' } })
  try {
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '展开')!.trigger('click'); await flushPromises()
    const childSignal=get.mock.calls.find(([path])=>path.includes('group_id='))![2] as AbortSignal
    await wrapper.setProps({ open: false })
    expect(childSignal.aborted).toBe(true)
    await wrapper.setProps({ open: true })
    if (outcome === 'success') finishChild(page([{ ...item('asset', 1, 'Stale.fit'), source_dataset_id: id(11) }]))
    else failChild(new Error('stale group failure'))
    await flushPromises()
    expect(wrapper.text()).toContain('正在读取回收站')
    expect(wrapper.text()).not.toContain('Stale.fit')
    expect(wrapper.text()).not.toContain('stale group failure')
    finishList(page([])); await flushPromises()
    expect(wrapper.text()).toContain('回收站为空')
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
  const wrapper = mount(LibraryTrashDialog, { props: { open: true, workspaceId:'trash-test-workspace' } })
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
  const wrapper = mount(LibraryTrashDialog, { props: { open: true, workspaceId:'trash-test-workspace' } })
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

it('aborts the old workspace read and rejects its late response', async()=>{
  let finishOld!: (value:unknown)=>void, finishNew!: (value:unknown)=>void
  get.mockImplementationOnce(()=>new Promise(resolve=>{finishOld=resolve}))
    .mockImplementationOnce(()=>new Promise(resolve=>{finishNew=resolve}))
  const wrapper=mount(LibraryTrashDialog,{props:{open:true,workspaceId:'old-workspace'}})
  try {
    await flushPromises()
    const oldSignal=get.mock.calls[0][2] as AbortSignal
    await wrapper.setProps({workspaceId:'new-workspace'});await flushPromises()
    expect(oldSignal.aborted).toBe(true)
    finishNew(page([item('asset',2,'New workspace.fit')]))
    await flushPromises()
    finishOld(page([item('asset',1,'Old workspace.fit')]))
    await flushPromises()
    expect(wrapper.text()).toContain('New workspace.fit')
    expect(wrapper.text()).not.toContain('Old workspace.fit')
  } finally {wrapper.unmount()}
})

it('discovers trash changes while idle and pauses refresh for a reviewed selection',async()=>{
  vi.useFakeTimers();focusManager.setFocused(true)
  get.mockResolvedValue(page([item('asset',1,'A.fit')]))
  const wrapper=mount(LibraryTrashDialog,{props:{open:true,workspaceId:'trash-test-workspace'}})
  try {
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(1)
    get.mockResolvedValue(page([item('asset',1,'A.fit'),item('asset',2,'B.fit')]))
    await vi.advanceTimersByTimeAsync(10_000);await flushPromises()
    expect(wrapper.text()).toContain('B.fit')
    expect(get).toHaveBeenCalledTimes(2)
    await wrapper.get('input[aria-label="选择 A.fit"]').setValue(true)
    await vi.advanceTimersByTimeAsync(20_000);await flushPromises()
    expect(get).toHaveBeenCalledTimes(2)
    expect(wrapper.get('input[aria-label="选择 A.fit"]').element).toHaveProperty('checked',true)
    await wrapper.setProps({open:false})
    await vi.advanceTimersByTimeAsync(20_000);await flushPromises()
    expect(get).toHaveBeenCalledTimes(2)
  } finally {wrapper.unmount();focusManager.setFocused(undefined);vi.useRealTimers()}
})

it.each(['root','group'])('keeps partial deletion facts after the %s list refresh without replaying deletion',async(scope)=>{
  let attempted=false
  const group={...item('dataset',100,'Group'),photo_count:21,member_asset_ids:Array.from({length:21},(_,i)=>id(i+1))}
  get.mockImplementation(async(path:string)=>{
    const query=new URL(path,'http://local.test').searchParams
    const target={...item('asset',1,'Locked.fit'),cleanup_status:attempted?'partial':'trash',cleanup_error:attempted?'File locked':null}
    if(scope==='root')return page([target])
    if(!query.has('group_id'))return page([group])
    return query.get('offset')==='20'?page([{...target,source_dataset_id:group.id}],21,20):page(Array.from({length:20},(_,i)=>({...item('asset',i+2,`Other ${i+2}.fit`),source_dataset_id:group.id})),21)
  })
  send.mockImplementation(async(path:string,_schema:unknown,_method:string,_body:{items:unknown[]})=>{
    if(path.endsWith('/delete-preview'))return {items:[item('asset',1,'Locked.fit')],tasks:[],references:[],managed_bytes:10,managed_file_count:1,photo_count:1,preview_fingerprint:'review'}
    attempted=true
    return {deleted_count:0,deleted_entry_count:0,deleted_file_count:0,deleted_bytes:0,missing_file_count:0,failed:[{id:id(1),error:'File locked'}]}
  })
  const wrapper=mount(LibraryTrashDialog,{props:{open:true,workspaceId:'trash-test-workspace'}})
  try {
    await flushPromises()
    if(scope==='group'){
      await wrapper.findAll('button').find(button=>button.text()==='展开')!.trigger('click');await flushPromises()
      await wrapper.findAll('button').find(button=>button.text()==='组内下一页')!.trigger('click');await flushPromises()
    }
    await wrapper.get('input[aria-label="选择 Locked.fit"]').setValue(true)
    await wrapper.findAll('button').find(button=>button.text()==='永久删除')!.trigger('click');await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='确认永久删除')!.trigger('click');await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('File locked')
    if(scope==='root')expect(wrapper.text()).toContain('部分清理（不可恢复）')
    expect(wrapper.findAll('button').find(button=>button.text()==='恢复')!.attributes('disabled')).toBeDefined()
    const deletes=send.mock.calls.filter(([path])=>path.endsWith('/trash/delete'))
    expect(deletes).toHaveLength(1)
    expect(deletes[0][3].preview_fingerprint).toBe('review')
    expect(get.mock.calls.length).toBeGreaterThan(1)
  } finally {wrapper.unmount()}
})

it('reports a failed trash read without claiming the trash is empty',async()=>{
  get.mockRejectedValue(new ApiClientError('Trash database unavailable','service',503,'DATABASE_UNAVAILABLE'))
  const wrapper=mount(LibraryTrashDialog,{props:{open:true,workspaceId:'trash-test-workspace'}})
  try {
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Trash database unavailable')
    expect(wrapper.text()).not.toContain('回收站为空')
    expect(get).toHaveBeenCalledTimes(1)
  } finally {wrapper.unmount()}
})

it('does not clamp a requested page using stale cached totals before its fresh reply',async()=>{
  let finishPage!: (value:unknown)=>void
  get.mockImplementation((path:string)=>{
    const offset=new URL(path,'http://local.test').searchParams.get('offset')
    return offset==='20'?new Promise(resolve=>{finishPage=resolve}):Promise.resolve(page(Array.from({length:20},(_,i)=>item('asset',i+1,`Page one ${i+1}.fit`)),41))
  })
  const Harness=defineComponent({setup(){
    const client=useQueryClient()
    client.setQueryData([...trashQueryKey('trash-test-workspace'),{limit:20,offset:20}],page([],19,20))
    return ()=>h(LibraryTrashDialog,{open:true,workspaceId:'trash-test-workspace'})
  }})
  const wrapper=mount(Harness)
  try {
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='下一页')!.trigger('click');await flushPromises()
    const signal=get.mock.calls.find(([path])=>path.includes('offset=20'))![2] as AbortSignal
    expect(signal.aborted).toBe(false)
    finishPage(page([item('asset',21,'Fresh page two.fit')],41,20));await flushPromises()
    expect(wrapper.text()).toContain('Fresh page two.fit')
    expect(wrapper.text()).toContain('21–21 / 41')
    expect(get).toHaveBeenCalledTimes(2)
  } finally {wrapper.unmount()}
})

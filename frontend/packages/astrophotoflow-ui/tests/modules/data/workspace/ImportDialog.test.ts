import {flushPromises,mount} from '@vue/test-utils'
import {beforeEach,describe,expect,it,vi} from 'vitest'
import ImportDialog from '@ui/modules/data/imports/ImportDialog.vue'

const {get,send,upload}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn(),upload:vi.fn()}))
vi.mock('@ui/modules/data/api/index',async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send),assetApi:{get,send,upload}}))

beforeEach(()=>{
  get.mockReset().mockResolvedValue({items:[],total:0,limit:200,offset:0})
  send.mockReset()
  upload.mockReset()
})

describe('import dialog defaults',()=>{
  it.each(['reopen','workspace'])('does not close a fresh %s import draft with an older acknowledgement or duplicate its request',async(change)=>{
    let finish!:(value:unknown)=>void
    send.mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
    const wrapper=mount(ImportDialog,{props:{workspaceId:'/one',open:true,files:[{path:'C:/synthetic/old.fits',name:'old.fits',size:4}],createDataset:true,datasetName:'Old'}})
    try{
      await flushPromises()
      await Promise.all([wrapper.get('form').trigger('submit'),wrapper.get('form').trigger('submit')]);await flushPromises()
      expect(send).toHaveBeenCalledTimes(1)
      if(change==='reopen')await wrapper.setProps({open:false})
      await wrapper.setProps({workspaceId:change==='workspace'?'/two':'/one',open:true,
        files:[{path:'C:/synthetic/new.fits',name:'new.fits',size:4}],datasetName:'Fresh'})
      finish({task_id:'00000000-0000-4000-8000-000000000001',status:'queued'});await flushPromises()
      expect(wrapper.emitted('submitted')).toBeUndefined()
      expect(wrapper.get<HTMLInputElement>('#import-dataset-name').element.value).toBe('Fresh')
      expect(send).toHaveBeenCalledTimes(1)
    }finally{wrapper.unmount()}
  })
  it('submits selected absolute paths without a configured root',async()=>{
    send.mockResolvedValue({task_id:'00000000-0000-4000-8000-000000000001',status:'queued'})
    const path='D:\\Night\\one.fits'
    const wrapper=mount(ImportDialog,{props:{workspaceId:'/test-workspace',open:true,files:[{path,name:'one.fits',size:4}]}})
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(send.mock.calls[0][3].sources).toEqual([{path}])
    expect(send.mock.calls[0][3].storage_mode).toBe('managed')
    expect(upload).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('clears prior metadata when a new import dialog opens',async()=>{
    const file={root_id:'science',path:'first.fits',name:'first.fits',size:4}
    const wrapper=mount(ImportDialog,{props:{workspaceId:'/test-workspace',open:false,files:[file],createDataset:true,datasetName:'M31'}})
    await wrapper.setProps({open:true})
    await flushPromises()
    const bin=wrapper.findAll('label').find(label=>label.text().startsWith('Bin'))!.get('select').element as HTMLSelectElement
    expect(Array.from(bin.options,value=>value.value)).toEqual(['',...Array.from({length:16},(_,index)=>String(index+1))])
    const datasetName=wrapper.findAll('label').find(label=>label.text().startsWith('图像组名称'))!.get('input')
    await wrapper.get('input[type="checkbox"]').setValue(true)
    const frameClass=wrapper.findAll('label').find(label=>label.text().startsWith('素材形态'))!.get('select')
    await datasetName.setValue('M31 session')
    await frameClass.setValue('masterframe')
    const frameType=wrapper.findAll('label').find(label=>label.text().startsWith('帧用途'))!.get('select')
    await frameType.setValue('dark')
    await wrapper.get('input[aria-label="单帧曝光（秒）"]').setValue('800')

    await wrapper.setProps({open:false})
    await wrapper.setProps({open:true,datasetName:'M42'})
    await flushPromises()

    expect(wrapper.findAll('label').find(label=>label.text().startsWith('图像组名称'))!.get('input').element).toHaveProperty('value','M42')
    expect(wrapper.findAll('label').some(label=>label.text().startsWith('素材形态'))).toBe(false)
    expect(wrapper.get('input[type="checkbox"]').element).toHaveProperty('checked',false)
    expect(wrapper.findAll('label').some(label=>label.text().startsWith('帧用途'))).toBe(false)
    expect(wrapper.text()).not.toContain('增益模式')
    expect(wrapper.text()).not.toContain('像素排列')
    expect(wrapper.findAll('input[type="number"]').every(input=>(input.element as HTMLInputElement).value==='')).toBe(true)
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('')
  })
})

describe('import overrides',()=>{
  it('omits blank manual values and classification so file metadata can supply them',async()=>{
    send.mockResolvedValue({task_id:'00000000-0000-4000-8000-000000000001',status:'queued'})
    upload.mockResolvedValue(undefined)
    const wrapper=mount(ImportDialog,{props:{workspaceId:'/test-workspace',open:false,files:[{root_id:'science',path:'one.fits',name:'one.fits',size:4}]}})
    await wrapper.setProps({open:true})
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    const body=send.mock.calls[0][3]
    expect(body).not.toHaveProperty('classification')
    expect(body.parameters).toEqual({})
    expect(body.storage_mode).toBe('managed')
    expect(body.sources).toEqual([{root_id:'science',path:'one.fits'}])
    expect(upload).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('submits a whole-batch manual classification including an intentional unknown frame type',async()=>{
    send.mockResolvedValue({task_id:'00000000-0000-4000-8000-000000000001',status:'queued'})
    upload.mockResolvedValue(undefined)
    const wrapper=mount(ImportDialog,{props:{workspaceId:'/test-workspace',open:false,files:[{root_id:'science',path:'one.fits',name:'one.fits',size:4}]}})
    await wrapper.setProps({open:true})
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await wrapper.findAll('label').find(label=>label.text().startsWith('素材形态'))!.get('select').setValue('masterframe')
    await wrapper.findAll('label').find(label=>label.text().startsWith('单帧曝光'))!.get('input').setValue('0')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(send.mock.calls[0][3].classification).toEqual({frame_class:'masterframe',frame_type:null})
    expect(send.mock.calls[0][3].parameters).toEqual({exposure_seconds:0})
    wrapper.unmount()
  })
})


it('imports direct equipment associations without adding capture defaults or a preset identity',async()=>{
  const camera={id:'00000000-0000-4000-8000-000000000003',kind:'camera',name:'My camera',model:null,notes:null,specs:{},status:'active',revision:2,created_at:'2026-11-02T00:00:00Z',updated_at:'2026-11-02T00:00:00Z'}
  get.mockImplementation(async(path:string)=>path.includes('/equipment?')?{items:[camera],total:1,limit:200,offset:0}:{items:[],total:0,limit:200,offset:0})
  send.mockResolvedValue({task_id:'00000000-0000-4000-8000-000000000001',status:'queued'})
  const wrapper=mount(ImportDialog,{props:{workspaceId:'/test-workspace',open:true,files:[{path:'D:/Night/one.fits',name:'one.fits',size:4}]}})
  await flushPromises()
  await wrapper.get('select[aria-label="相机"]').setValue(camera.id)
  await wrapper.get('form').trigger('submit');await flushPromises()
  expect(send.mock.calls[0][3]).toMatchObject({equipment:{choice:{source:'devices',camera:{equipment_id:camera.id,expected_revision:2}},fields:['camera']},parameters:{}})
  expect(send.mock.calls[0][3]).not.toHaveProperty('capture_preset_id')
  expect(send.mock.calls[0][3].parameters).not.toHaveProperty('sensor_temperature_c')
  wrapper.unmount()
})

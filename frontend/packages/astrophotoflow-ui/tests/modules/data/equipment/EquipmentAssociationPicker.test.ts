import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import EquipmentAssociationPicker from '@ui/modules/data/equipment/EquipmentAssociationPicker.vue'
import type { Equipment, EquipmentSetup } from '@ui/modules/data/api/contracts'

const {get} = vi.hoisted(() => ({get:vi.fn()}))
vi.mock('@ui/modules/data/api/index',async () => ({catalogApi:(await import('../../../fixtures/library-api')).createCatalogApiFixture(get)}))
const id = (n:number) => '00000000-0000-4000-8000-'+String(n).padStart(12,'0')
const timestamp = '2026-11-02T00:00:00Z'
const camera:Equipment = {id:id(1),kind:'camera',name:'Camera',model:null,notes:null,specs:{},status:'active',revision:3,created_at:timestamp,updated_at:timestamp}
const telescope:Equipment = {...camera,id:id(2),kind:'telescope',name:'Scope',specs:{optical_accessories:[{id:id(9),name:'Reducer',factor:0.7}]}}
const mountDevice:Equipment = {id:id(3),kind:'mount',name:'Mount',model:null,notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp}
const filters:Equipment[] = [4,5].map(n => ({...camera,id:id(n),kind:'filter',name:'Physical filter '+n,specs:{channel:'H'}}))
const setup:EquipmentSetup = {id:id(6),name:'Rig',notes:null,status:'active',revision:2,created_at:timestamp,updated_at:timestamp,components:[camera,telescope,mountDevice,...filters].map((row,index) => ({id:id(100+index),source:'registered',equipment_id:row.id}))}
let wrapper:ReturnType<typeof mount>
beforeEach(() => {
  get.mockReset().mockImplementation(async (path:string) => {
    const rows = path.includes('/equipment-setups?') ? [setup] : [camera,telescope,mountDevice,...filters]
    return {items:rows,total:rows.length,limit:200,offset:0}
  })
})
afterEach(() => wrapper?.unmount())
it('associates direct devices and an accessory with revisions but no capture parameter defaults',async () => {
  wrapper=mount(EquipmentAssociationPicker,{props:{workspaceId:'/test-workspace'}})
  await flushPromises()
  await wrapper.get('select[aria-label="相机"]').setValue(camera.id)
  await wrapper.get('select[aria-label="望远镜"]').setValue(telescope.id)
  await wrapper.get('select[aria-label="光学附件"]').setValue(id(9))
  await wrapper.get('select[aria-label="赤道仪"]').setValue(mountDevice.id)
  expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toEqual({choice:{source:'devices',camera:{equipment_id:camera.id,expected_revision:3},telescope:{equipment_id:telescope.id,expected_revision:3},mount:{equipment_id:mountDevice.id,expected_revision:1},optical_accessory_id:id(9)},fields:['camera','telescope','mount','optical_accessory']})
  expect(wrapper.text()).not.toContain('拍摄预设')
  expect(get.mock.calls.every(([path]) => !String(path).includes('presets'))).toBe(true)
})
it('requires an explicit actual filter for a multiple-filter setup and preserves physical member identity',async () => {
  wrapper=mount(EquipmentAssociationPicker,{props:{workspaceId:'/test-workspace'}})
  await flushPromises()
  await wrapper.get('select').setValue('setup')
  await wrapper.get('select[aria-label="导入设备组合"]').setValue(setup.id)
  expect(wrapper.emitted('valid')?.at(-1)).toEqual([false])
  expect(wrapper.text()).toContain('Physical filter 4')
  expect(wrapper.text()).toContain('Physical filter 5')
  await wrapper.get('select[aria-label="滤镜"]').setValue(id(104))
  expect(wrapper.emitted('valid')?.at(-1)).toEqual([true])
  expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toMatchObject({choice:{source:'setup',setup_id:setup.id,expected_revision:2,filter:{mode:'member',member_id:id(104)}}})
  await wrapper.get('select[aria-label="滤镜"]').setValue('none')
  expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toMatchObject({choice:{filter:{mode:'none'}}})
})

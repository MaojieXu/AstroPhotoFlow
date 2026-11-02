import {mount,flushPromises} from '@vue/test-utils'
import {expect,it,vi} from 'vitest'
import EquipmentDeleteDialog from '@ui/modules/data/equipment/EquipmentDeleteDialog.vue'
const api=vi.hoisted(()=>({preview:vi.fn(),remove:vi.fn()}))
vi.mock('@ui/modules/data/api',()=>({trashApi:{equipmentPreview:api.preview,equipmentRemove:api.remove}}))
const id=(n:number)=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0')
it('keeps a new confirmation busy when an older scope completes and deletes only its frozen preview',async()=>{
 api.preview.mockImplementation(async(body)=>({preview_fingerprint:body.items[0].id,items:body.items.map((item:{id:string})=>({...item,name:item.id})),dependencies:[]}))
 let old!:(value:unknown)=>void,newer!:(value:unknown)=>void
 api.remove.mockImplementationOnce(()=>new Promise(resolve=>old=resolve)).mockImplementationOnce(()=>new Promise(resolve=>newer=resolve))
 const wrapper=mount(EquipmentDeleteDialog,{props:{workspaceId:'/one',viewKey:'first',items:[{entry_type:'equipment',id:id(1),revision:1}]}})
 try{
  await flushPromises();await wrapper.get('.apf-equipment-dialog-footer button:last-child').trigger('click');await flushPromises()
  await wrapper.setProps({viewKey:'second',items:[{entry_type:'equipment',id:id(2),revision:1}]});await flushPromises()
  await wrapper.get('.apf-equipment-dialog-footer button:last-child').trigger('click');await flushPromises()
  expect(api.remove).toHaveBeenCalledTimes(2)
  old({});await flushPromises()
  expect(wrapper.get('.apf-equipment-dialog-footer button:last-child').attributes('disabled')).toBeDefined()
  expect(wrapper.emitted('deleted')).toBeUndefined()
  expect(api.remove.mock.calls[1]![0]).toEqual({items:[{entry_type:'equipment',id:id(2),revision:1}],preview_fingerprint:id(2)})
  newer({});await flushPromises()
  expect(wrapper.emitted('deleted')).toHaveLength(1)
 }finally{wrapper.unmount()}
})

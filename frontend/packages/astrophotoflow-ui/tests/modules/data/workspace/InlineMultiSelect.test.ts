import {flushPromises,mount} from '@vue/test-utils'
import {describe,expect,it,vi} from 'vitest'
import {nextTick} from 'vue'
import InlineMultiSelect from '@ui/modules/data/workspace/InlineMultiSelect.vue'

async function open(wrapper:ReturnType<typeof mount>){
  const button=wrapper.get('button').element
  button.dispatchEvent(new MouseEvent('click',{bubbles:true,detail:1}))
  await nextTick()
  button.dispatchEvent(new MouseEvent('click',{bubbles:true,detail:2}))
  await nextTick()
  button.dispatchEvent(new MouseEvent('dblclick',{bubbles:true,cancelable:true}))
  await nextTick()
}

describe('inline multi-select editing',()=>{
  it('preserves selected IDs and saves a changed set once',async()=>{
    const save=vi.fn().mockResolvedValue(undefined)
    const wrapper=mount(InlineMultiSelect,{props:{
      value:['profile-1'],choices:[{value:'profile-1',label:'Profile 1'},{value:'profile-2',label:'Profile 2'}],save
    }})
    await open(wrapper)
    const select=wrapper.get('select')
    expect((select.element as HTMLSelectElement).selectedOptions[0].value).toBe('profile-1')
    await select.setValue(['profile-1','profile-2'])
    await select.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(save).toHaveBeenCalledOnce()
    expect(new Set(save.mock.calls[0][0])).toEqual(new Set(['profile-1','profile-2']))
  })

  it('keeps the list open while it replaces the focused display button',async()=>{
    const save=vi.fn()
    const wrapper=mount(InlineMultiSelect,{props:{
      value:['profile-1'],choices:[{value:'profile-1',label:'Profile 1'}],save
    },attachTo:document.body})
    wrapper.get('button').element.focus()
    await open(wrapper)
    expect((wrapper.get('select').element as HTMLSelectElement).selectedOptions[0].value).toBe('profile-1')
    expect(save).not.toHaveBeenCalled()
  })

  it('retains the draft on failure and cancels it with Escape',async()=>{
    const save=vi.fn().mockRejectedValue(new Error('revision conflict'))
    const wrapper=mount(InlineMultiSelect,{props:{
      value:['profile-1'],choices:[{value:'profile-1',label:'Profile 1'},{value:'profile-2',label:'Profile 2'}],save
    }})
    await open(wrapper)
    const select=wrapper.get('select')
    await select.setValue(['profile-2'])
    await select.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect((wrapper.get('select').element as HTMLSelectElement).selectedOptions[0].value).toBe('profile-2')
    expect(wrapper.text()).toContain('revision conflict')
    await wrapper.get('select').trigger('keydown',{key:'Escape'})
    expect(wrapper.text()).toContain('Profile 1')
    expect(save).toHaveBeenCalledOnce()
  })
})

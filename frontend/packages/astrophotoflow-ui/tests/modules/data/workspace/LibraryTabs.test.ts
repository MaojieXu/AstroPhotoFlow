import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { describe, expect, it } from 'vitest'
import LibraryTabs from '@ui/modules/data/workspace/LibraryTabs.vue'
import { libraryControlsKey } from '@ui/modules/data/workspace/libraryControls'

const native = defineComponent({ setup(_, { slots, attrs }) { return () => h('div', attrs, slots.default?.()) } })
describe('library and equipment navigation alignment', () => {
  it('left aligns the native tab list and keeps equipment tab order', () => {
    const wrapper = mount(LibraryTabs, {
      props: { value: 'equipment-setups', label: '设备与资料类别', options: [{value:'equipment-setups',label:'设备组合'},{value:'equipment',label:'我的设备'}] },
      global: { provide: { [libraryControlsKey as symbol]: { tabs:native,tabsList:native,tabsTrigger:native } } }
    })
    expect(wrapper.get('[aria-label="设备与资料类别"]').attributes('style')).toContain('justify-content: flex-start')
    expect(wrapper.text().indexOf('设备组合')).toBeLessThan(wrapper.text().indexOf('我的设备'))
    wrapper.unmount()
  })
})

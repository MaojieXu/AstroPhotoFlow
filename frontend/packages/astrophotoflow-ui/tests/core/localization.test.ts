import { computed } from 'vue'
import { createI18n } from 'vue-i18n'
import { describe, expect, it } from 'vitest'

import { configureUII18n, uiMessages, uiT } from '../../src/core/i18n'
import { displayLabel } from '../../src/modules/data/workspace/presentation'
import { nodeCapabilitySchema } from '../../src/modules/nodes/client'

describe('workspace display language', () => {
  it('updates existing computed labels without recreating their data', () => {
    const i18n = createI18n({ legacy: false, locale: 'zh', messages: uiMessages })
    configureUII18n((key, values) => i18n.global.t(key, values))
    const label = computed(() => displayLabel('light'))
    expect(label.value).toBe('亮场')
    i18n.global.locale.value = 'en'
    expect(label.value).toBe('Light')
    i18n.global.locale.value = 'zh'
    expect(label.value).toBe('亮场')
  })

  it.each([0, 1, 3])('keeps the exact record count %s in either language', count => {
    const i18n = createI18n({ legacy: false, locale: 'en', messages: uiMessages })
    configureUII18n((key, values) => i18n.global.t(key, values))
    expect(uiT('apfUi.records_value', { p0: count })).toBe(`Records: ${count}`)
    i18n.global.locale.value = 'zh'
    expect(uiT('apfUi.records_value', { p0: count })).toBe(`${count} 条记录`)
  })

  it('ships the same nonempty keys and interpolation parameters in both languages', () => {
    const en = uiMessages.en.apfUi
    const zh = uiMessages.zh.apfUi
    expect(Object.keys(en).sort()).toEqual(Object.keys(zh).sort())
    for (const key of Object.keys(en) as Array<keyof typeof en>) {
      expect(en[key].trim()).not.toBe('')
      expect((en[key].match(/\{p\d+\}/g) ?? []).sort()).toEqual((zh[key].match(/\{p\d+\}/g) ?? []).sort())
    }
    expect(nodeCapabilitySchema.shape.display.parse(undefined)).toEqual({})
  })
})

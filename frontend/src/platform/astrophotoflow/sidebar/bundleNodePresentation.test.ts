import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, onTestFinished } from 'vitest'

import { mergeBundleNodeI18n, resolveNodeCategoryLabel, setActiveLocale } from '@/i18n'
import { ComfyNodeDefImpl, buildNodeDefTree } from '@/stores/nodeDefStore'
import { NodeSearchService } from '@/services/nodeSearchService'
import { normalizeI18nKey } from '@/utils/formatUtil'

describe('Bundle node presentation', () => {
  it('keeps category identity and bilingual search through language changes and removal', async () => {
    setActivePinia(createPinia())
    const type = 'APF_00000000000040008000000000000555'
    const path = 'siril/stretch-color/stretch-transforms'
    const enName = 'Generalized Hyperbolic Stretch (ght)'
    const zhName = '广义双曲拉伸（ght）'
    const definition = new ComfyNodeDefImpl({
      name: type, display_name: enName, category: path,
      search_aliases: [enName, zhName, 'ght'],
      python_module: 'custom_nodes.siril', description: '',
      input: {}, output: [], output_name: [], output_is_list: [], output_node: false
    })
    const categories = (main: string, child: string) => ({
      siril: 'Siril',
      [normalizeI18nKey('siril/stretch-color')]: main,
      [normalizeI18nKey(path)]: child
    })
    mergeBundleNodeI18n({
      en: { [normalizeI18nKey(type)]: { display_name: enName } },
      zh: { [normalizeI18nKey(type)]: { display_name: zhName } }
    }, {
      en: categories('Stretch and Color', 'Stretch Transforms'),
      zh: categories('拉伸与色彩', '拉伸变换')
    })
    onTestFinished(async () => {
      mergeBundleNodeI18n({})
      await setActiveLocale('en')
    })
    const keys: string[] = []
    for (const [locale, expected] of [['en', 'Stretch Transforms'], ['zh', '拉伸变换']] as const) {
      await setActiveLocale(locale)
      const tree = buildNodeDefTree([definition])
      const subcategory = tree.children![0].children![0].children![0]
      expect(subcategory.label).toBe(expected)
      keys.push(subcategory.key)
      expect(definition.category).toBe(path)
      const search = new NodeSearchService([definition])
      for (const query of ['Generalized Hyperbolic', '广义双曲拉伸', 'ght']) {
        expect(search.searchNode(query).map(node => node.name)).toContain(type)
      }
    }
    expect(keys).toEqual(['root/' + path, 'root/' + path])
    mergeBundleNodeI18n({})
    for (const locale of ['en', 'zh'] as const) {
      await setActiveLocale(locale)
      expect(resolveNodeCategoryLabel(path, 'stretch-transforms')).toBe('stretch-transforms')
    }
  })
})

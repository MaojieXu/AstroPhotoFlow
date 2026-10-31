import { config } from '@vue/test-utils'
import { beforeEach } from 'vitest'
import { createI18n } from 'vue-i18n'

import { configureUII18n, uiMessages } from '../src/core/i18n'

const i18n = createI18n({ legacy: false, locale: 'zh', fallbackLocale: 'en', messages: uiMessages })
config.global.plugins = [...(config.global.plugins ?? []), i18n]
configureUII18n((key, values) => i18n.global.t(key, values))
beforeEach(() => {
  i18n.global.locale.value = 'zh'
  configureUII18n((key, values) => i18n.global.t(key, values))
})

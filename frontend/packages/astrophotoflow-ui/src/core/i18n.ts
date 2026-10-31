import en from './locales/en.json'
import zh from './locales/zh.json'

export const uiMessages = { en: { apfUi: en }, zh: { apfUi: zh } }

type UITranslator = (key: string, values: Record<string, unknown>) => string
let translate: UITranslator | undefined

export function configureUII18n(value: UITranslator) {
  translate = value
}

export function uiT(key: string, values: Record<string, unknown> = {}) {
  if (!translate) throw new Error('AstroPhotoFlow UI requires the host i18n composer.')
  return translate(key, values)
}

import { readFileSync } from 'node:fs'
import type { Plugin } from 'vite'

const markPath = '/src/assets/astrophotoflow.svg'
const mark = readFileSync(
  new URL('../../src/assets/astrophotoflow.svg', import.meta.url),
  'utf8'
).replace(/<style>[\s\S]*?<\/style>/, '')

const publicAssets = [
  'assets/CREDIT.txt',
  'assets/sorted-custom-node-map.json',
  'assets/images/astrophotoflow-192.png',
  'assets/images/astrophotoflow-512.png',
  'assets/images/default-template.png',
  'cursor/colorSelect.png',
  'cursor/paintBucket.png',
  'fonts/inter-latin-italic.woff2',
  'fonts/inter-latin-normal.woff2',
  'fonts/materialdesignicons-webfont.woff2',
  'icons/social/github.svg',
  'materialdesignicons.min.css'
]

export function astrophotoflowBrand(): Plugin {
  return {
    name: 'astrophotoflow-brand',
    transformIndexHtml: {
      order: 'pre',
      handler(html) {
        return html
          .replace(
            'type="image/x-icon" href="/assets/favicon.ico"',
            `type="image/svg+xml" href="${markPath}"`
          )
          .replace('href="manifest.json"', 'href="manifest.astrophotoflow.json"')
          .replace(
            /(<div id="splash-loader"[^>]*>\s*)<svg\b[\s\S]*?<\/svg>/,
            (_, opening: string) =>
              opening.replace('Loading ComfyUI', 'Loading AstroPhotoFlow') +
              mark.replace('<svg ', '<svg aria-hidden="true" style="width:80px" ')
          )
          .replace(
            "el.style.background = bg",
            `if (navigator.language.startsWith('zh')) {
            el.setAttribute('aria-label', '正在加载 AstroPhotoFlow')
          }
          el.style.background = bg`
          )
      }
    },
    generateBundle() {
      for (const fileName of publicAssets) {
        this.emitFile({
          type: 'asset',
          fileName,
          source: readFileSync(new URL(`../../public/${fileName}`, import.meta.url))
        })
      }
    }
  }
}

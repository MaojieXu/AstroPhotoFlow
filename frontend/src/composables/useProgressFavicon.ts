import { useFavicon } from '@vueuse/core'
import { watch } from 'vue'

import astroPhotoFlowMark from '@/assets/astrophotoflow.svg?no-inline'
import markSource from '@/assets/astrophotoflow.svg?raw'
import { isCloud, isDesktop } from '@/platform/distribution/types'
import { useExecutionStore } from '@/stores/executionStore'

export const useProgressFavicon = () => {
  const isLocalWorkbench = !isCloud && !isDesktop
  const defaultFavicon = isLocalWorkbench
    ? astroPhotoFlowMark
    : '/assets/images/favicon_progress_16x16/frame_9.png'
  const favicon = useFavicon(defaultFavicon)
  const executionStore = useExecutionStore()
  const totalFrames = 10

  watch(
    [() => executionStore.executionProgress, () => executionStore.isIdle],
    ([progress, isIdle]) => {
      if (isIdle) {
        favicon.value = defaultFavicon
      } else if (isLocalWorkbench) {
        const width = Math.max(8, Math.min(100, Math.round(progress * 100)))
        const svg = markSource.replace(
          '</svg>',
          `<rect y="94" width="${width}" height="6"/></svg>`
        )
        favicon.value = `data:image/svg+xml,${encodeURIComponent(svg)}`
      } else {
        const frame = Math.min(
          Math.max(0, Math.floor(progress * totalFrames)),
          totalFrames - 1
        )
        favicon.value = `/assets/images/favicon_progress_16x16/frame_${frame}.png`
      }
    }
  )
}

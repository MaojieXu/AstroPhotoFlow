import type { MaybeRefOrGetter } from 'vue'
import { computed, ref, toValue, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { nodeHelpService } from '@/services/nodeHelpService'
import type { ComfyNodeDefImpl } from '@/stores/nodeDefStore'
import { renderMarkdownToHtml } from '@/utils/markdownRendererUtil'
import { getNodeHelpBaseUrl } from '@/workbench/utils/nodeHelpUtil'
import { resolveNodeDefText, te } from '@/i18n'
import { normalizeI18nKey } from '@/utils/formatUtil'

/**
 * Composable for fetching and rendering node help content.
 * Creates independent state for each usage, allowing multiple panels
 * to show help content without interfering with each other.
 *
 * @param nodeRef - Reactive reference to the node to show help for
 * @returns Reactive help content state and rendered HTML
 */
export function useNodeHelpContent(
  nodeRef: MaybeRefOrGetter<ComfyNodeDefImpl | null>
) {
  const { locale } = useI18n()

  const helpContent = ref<string>('')
  const isLoading = ref<boolean>(false)
  const error = ref<string | null>(null)

  let currentRequest: Promise<string> | null = null

  const baseUrl = computed(() => {
    const node = toValue(nodeRef)
    if (!node) return ''
    return getNodeHelpBaseUrl(node)
  })

  const renderedHelpHtml = computed(() => {
    return renderMarkdownToHtml(helpContent.value, baseUrl.value)
  })
  const inlineHelp = computed(() => {
    const node = toValue(nodeRef)
    if (node && te(`nodeDefs.${normalizeI18nKey(node.name)}.help`)) {
      return resolveNodeDefText('help', node.name, node.help)
    }
    return undefined
  })

  // Watch for node changes and fetch help content
  watch(
    [() => toValue(nodeRef), locale, inlineHelp],
    async ([node, , inline]) => {
      currentRequest = null
      helpContent.value = ''
      error.value = null
      isLoading.value = false

      if (inline !== undefined) {
        helpContent.value = inline
        return
      }

      if (node) {
        isLoading.value = true
        const request = (currentRequest = nodeHelpService.fetchNodeHelp(
          node,
          locale.value || 'en'
        ))

        try {
          const content = await request
          if (currentRequest !== request) return
          helpContent.value = content
        } catch (e: unknown) {
          if (currentRequest !== request) return
          error.value = e instanceof Error ? e.message : String(e)
          helpContent.value = node.description || ''
        } finally {
          if (currentRequest === request) {
            currentRequest = null
            isLoading.value = false
          }
        }
      }
    },
    { immediate: true }
  )

  return {
    helpContent,
    isLoading,
    error,
    baseUrl,
    renderedHelpHtml
  }
}

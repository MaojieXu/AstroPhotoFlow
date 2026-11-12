import { onScopeDispose, shallowRef } from 'vue'
import { ApiClientError } from '../../../core/api/errors'
import { uiT } from '../../../core/i18n'
import type { MediaViewerRequest } from '../api/media'
import { datasetMemberAt, readMemberPage } from '../datasets/members'
import { assetPreview, datasetReference, materialPreviewBase, resolveMaterialRecord } from '../library/materialRecords'
import type { PreviewMember } from '../library/materialRecords'
import type { PreviewPhoto } from './previewTypes'

export interface LibraryPreviewOptions {
  nativeViewer: () => boolean
  waitForEdits: () => Promise<boolean>
  onError: (cause: unknown) => void
}

export function useLibraryPreview(options: LibraryPreviewOptions) {
  const photo = shallowRef<PreviewPhoto>()
  const media = shallowRef<MediaViewerRequest>()
  let active: AbortController | undefined
  let pending: AbortController | undefined

  function close() {
    pending?.abort()
    pending = undefined
    active?.abort()
    active = undefined
    photo.value = undefined
    media.value = undefined
  }

  async function open(value: unknown) {
    pending?.abort()
    const current = pending = new AbortController()
    try {
      const record = resolveMaterialRecord(value)
      if (!record || !await options.waitForEdits() || current !== pending || current.signal.aborted) return
      const group = datasetReference(record)
      let first: PreviewMember | undefined
      if (options.nativeViewer() && group) {
        const page = await readMemberPage(group, {limit:1,offset:0,sort_by:'position',order:'asc'}, current.signal)
        if (current !== pending || current.signal.aborted || !page.total) return
        const initial = page.items[0]
        if (!initial) throw new ApiClientError(uiT('apfUi.fixed_member_is_out_of_range'), 'contract')
        active?.abort()
        active = current
        pending = undefined
        photo.value = undefined
        media.value = {index:0,total:page.total,member:async(index,signal)=>{
          const scoped = AbortSignal.any([current.signal,signal])
          scoped.throwIfAborted()
          const member = index === 0 ? initial : await datasetMemberAt(group,index,scoped)
          scoped.throwIfAborted()
          return {title:member.asset.name,basePath:materialPreviewBase(record,member.asset),selection:{dataset_id:group.id}}
        }}
        return
      }
      first = group ? (await datasetMemberAt(group,0,current.signal)).asset : assetPreview(record)
      if (current !== pending || current.signal.aborted || !first) return
      active?.abort()
      active = current
      pending = undefined
      if (options.nativeViewer()) {
        photo.value = undefined
        const member = first
        media.value = {index:0,total:1,member:async(_index,signal)=>{
          AbortSignal.any([current.signal,signal]).throwIfAborted()
          return {title:member.name,basePath:materialPreviewBase(record,member),
            selection:'member_position' in record && 'dataset_id' in record ? {dataset_id:record.dataset_id}:undefined}
        }}
      } else {
        media.value = undefined
        photo.value = {assetId:first.id,title:first.name,basePath:materialPreviewBase(record,first)}
      }
    } catch (cause) {
      if (current === pending && !current.signal.aborted) options.onError(cause)
    }
  }

  onScopeDispose(close)
  return {photo,media,open,close}
}

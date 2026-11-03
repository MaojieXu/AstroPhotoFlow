import { onScopeDispose, shallowRef } from 'vue'
import { ApiClientError } from '../../../core/api/errors'
import { uiT } from '../../../core/i18n'
import type { MediaViewerRequest } from '../api/media'
import { fixedMemberAt, readMemberPage } from '../datasets/members'
import { fixedAssetPreview, fixedDatasetReference, materialPreviewBase, resolveMaterialRecord } from '../library/materialRecords'
import type { FixedPreviewMember } from '../library/materialRecords'
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

  function close() {
    active?.abort()
    active = undefined
    photo.value = undefined
    media.value = undefined
  }

  async function open(value: unknown) {
    close()
    const current = active = new AbortController()
    try {
      const record = resolveMaterialRecord(value)
      if (!record || !await options.waitForEdits() || current !== active || current.signal.aborted) return
      const group = fixedDatasetReference(record)
      let first: FixedPreviewMember | undefined
      if (options.nativeViewer() && group) {
        const page = await readMemberPage(group, {limit:1,offset:0,sort_by:'position',order:'asc'}, current.signal)
        if (current !== active || current.signal.aborted || !page.total) return
        const initial = page.items[0]
        if (!initial) throw new ApiClientError(uiT('apfUi.fixed_member_is_out_of_range'), 'contract')
        media.value = {index:0,total:page.total,member:async(index,signal)=>{
          const scoped = AbortSignal.any([current.signal,signal])
          scoped.throwIfAborted()
          const member = index === 0 ? initial : await fixedMemberAt(group,index,scoped)
          scoped.throwIfAborted()
          return {title:member.asset.name,basePath:materialPreviewBase(record,member),selection:{dataset_version_id:group.versionId}}
        }}
        return
      }
      first = group ? await fixedMemberAt(group,0,current.signal) : fixedAssetPreview(record)
      if (current !== active || current.signal.aborted || !first) return
      if (options.nativeViewer()) {
        const member = first
        media.value = {index:0,total:1,member:async(_index,signal)=>{
          AbortSignal.any([current.signal,signal]).throwIfAborted()
          return {title:member.asset.name,basePath:materialPreviewBase(record,member),
            selection:'member_position' in record && 'dataset_version_id' in record ? {dataset_version_id:record.dataset_version_id}:undefined}
        }}
      } else photo.value = {assetId:first.asset.id,versionId:first.version.id,title:first.asset.name,basePath:materialPreviewBase(record,first)}
    } catch (cause) {
      if (current === active && !current.signal.aborted) options.onError(cause)
    }
  }

  onScopeDispose(close)
  return {photo,media,open,close}
}

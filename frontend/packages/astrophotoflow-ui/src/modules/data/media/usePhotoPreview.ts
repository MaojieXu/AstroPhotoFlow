import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, onScopeDispose, shallowRef, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { uiT } from '../../../core/i18n'
import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { displayPreviewApi } from '../api'
import type { PreviewPhoto } from './previewTypes'

type Target = { workspaceId: string; photo: PreviewPhoto; base: string; controller: AbortController }

export function usePhotoPreview(workspace: MaybeRefOrGetter<string>, photo: MaybeRefOrGetter<PreviewPhoto | undefined>, updated: (value: PreviewPhoto) => void) {
  const connectionReady = useQueryAvailability()
  const cache = useQueryClient()
  const target = computed<Target | undefined>(() => {
    const current = toValue(photo), workspaceId = toValue(workspace)
    return current && workspaceId ? {workspaceId,photo:current,
      base:current.basePath,
      controller:new AbortController()} : undefined
  })
  const prepared = shallowRef<Target>()
  const protocolError = shallowRef('')
  const imageUrl = shallowRef('')
  let ensuredAfterPlainPreview = false
  const key = (current: Target) => [...workspaceQueryKey(current.workspaceId),'media','display-preview',current.base] as const
  const prepare = useMutation({
    mutationFn: (current: Target) => displayPreviewApi.prepare(current.base,current.controller.signal),
    retry:false
  })
  const status = useQuery({
    queryKey:computed(()=>target.value?key(target.value):['display-preview-idle']),
    enabled:computed(()=>connectionReady.value&&Boolean(target.value)&&prepared.value===target.value),
    queryFn:({signal})=>{
      const current=target.value
      if(!current)throw new Error('Display preview requires a fixed target')
      return displayPreviewApi.status(current.base,AbortSignal.any([signal,current.controller.signal]))
    },
    staleTime:Infinity,
    refetchInterval:query=>!query.state.error&&query.state.data?.status==='generating'?500:false
  })
  const available = computed(()=>prepared.value===target.value&&status.data.value?.status==='available'&&Boolean(status.data.value.stretch))
  const image = useQuery({
    queryKey:computed(()=>target.value?[...key(target.value),'image',status.data.value?.stretch]:['display-image-idle']),
    enabled:computed(()=>connectionReady.value&&available.value),
    queryFn:({signal})=>{
      const current=target.value
      if(!current)throw new Error('Display image requires a fixed target')
      return displayPreviewApi.image(current.base,AbortSignal.any([signal,current.controller.signal]))
    },
    staleTime:0,
    gcTime:0
  })

  function releaseImage() {
    if(imageUrl.value)URL.revokeObjectURL(imageUrl.value)
    imageUrl.value=''
  }
  async function ensure(current: Target) {
    if (!connectionReady.value) return
    try {
      const state=await prepare.mutateAsync(current)
      if(target.value!==current||current.controller.signal.aborted)return
      cache.setQueryData(key(current),state)
      prepared.value=current
    }catch{/* Mutation diagnostics belong to this view; generation is never replayed automatically. */}
  }
  async function retry() {
    const current=target.value
    if(!connectionReady.value||!current||prepare.isPending.value)return
    prepared.value=undefined;protocolError.value='';ensuredAfterPlainPreview=false;releaseImage()
    await cache.cancelQueries({queryKey:key(current)})
    await ensure(current)
  }
  watch(target,(current,previous)=>{
    previous?.controller.abort();prepared.value=undefined;protocolError.value='';ensuredAfterPlainPreview=false
    prepare.reset();releaseImage()
    if(current)void ensure(current)
  },{immediate:true,flush:'sync'})
  watch([status.data,prepared,connectionReady],([state,ready])=>{
    if (!connectionReady.value) return
    const current=target.value
    if(!current||ready!==current||state?.status!=='available'||state.stretch)return
    if(ensuredAfterPlainPreview){protocolError.value=uiT('apfUi.full_size_preview_is_not_ready_please_try_again');return}
    ensuredAfterPlainPreview=true;prepared.value=undefined
    void ensure(current)
  })
  watch([image.data,image.dataUpdatedAt,image.isFetching,available],([blob,_updated,fetching,ready])=>{
    if(!ready||fetching||!blob||!target.value)return
    releaseImage();imageUrl.value=URL.createObjectURL(blob);updated(target.value.photo)
  })
  const error=computed(()=>{
    const cause=prepare.error.value??status.error.value??image.error.value
    if(cause)return cause instanceof Error?cause.message:uiT('apfUi.could_not_read_the_full_size_preview')
    if(protocolError.value)return protocolError.value
    const state=status.data.value
    return prepared.value===target.value&&state&&state.status!=='available'&&state.status!=='generating'
      ?state.error?.message??uiT('apfUi.full_size_preview_is_not_ready_please_try_again'):''
  })
  const loading=computed(()=>Boolean(target.value)&&!error.value&&(!imageUrl.value||prepare.isPending.value||image.isFetching.value))
  onScopeDispose(()=>{target.value?.controller.abort();releaseImage()})
  return {imageUrl,loading,error,retry}
}

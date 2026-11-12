import { computed } from 'vue'
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { mutationApi } from '../api'
import { projectQueryKey } from './queries'
import { workspaceQueryKey } from '../../../core/query/keys'

type ProjectWrite = { workspaceId: string; projectId: string }

export function useCreateProject() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: ({body}: {workspaceId:string;body:Parameters<typeof mutationApi.createProject>[0]}) => mutationApi.createProject(body),
    retry:false,
    onSettled:(_data,_error,{workspaceId})=>cache.invalidateQueries({queryKey:projectQueryKey(workspaceId)})
  })
}

export function useUpdateProject() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: ({ projectId, body }: ProjectWrite & { body: Parameters<typeof mutationApi.patchProject>[1] }) => mutationApi.patchProject(projectId, body),
    retry: false,
    onSettled: (_data, _error, { workspaceId }) => Promise.all([
      cache.invalidateQueries({queryKey:projectQueryKey(workspaceId)}),
      cache.invalidateQueries({queryKey:[...workspaceQueryKey(workspaceId),'trash']})
    ])
  })
}

export function useProjectReferences() {
  const cache = useQueryClient()
  const settled = (_data: unknown, _error: unknown, request: ProjectWrite) =>
    cache.invalidateQueries({queryKey:projectQueryKey(request.workspaceId)})
  const addAsset = useMutation({
    mutationFn: (request: ProjectWrite & {body: Parameters<typeof mutationApi.addProjectAsset>[1]}) => mutationApi.addProjectAsset(request.projectId,request.body),
    retry:false,onSettled:settled
  })
  const addDataset = useMutation({
    mutationFn: (request: ProjectWrite & {body: Parameters<typeof mutationApi.addProjectDataset>[1]}) => mutationApi.addProjectDataset(request.projectId,request.body),
    retry:false,onSettled:settled
  })
  const removeAsset = useMutation({
    mutationFn: (request: ProjectWrite & {referenceId: string; body: Parameters<typeof mutationApi.removeProjectAsset>[2]}) => mutationApi.removeProjectAsset(request.projectId,request.referenceId,request.body),
    retry:false,onSettled:settled
  })
  const removeDataset = useMutation({
    mutationFn: (request: ProjectWrite & {referenceId: string; body: Parameters<typeof mutationApi.removeProjectDataset>[2]}) => mutationApi.removeProjectDataset(request.projectId,request.referenceId,request.body),
    retry:false,onSettled:settled
  })
  const pending = computed(()=>addAsset.isPending.value||addDataset.isPending.value||removeAsset.isPending.value||removeDataset.isPending.value)
  return {addAsset,addDataset,removeAsset,removeDataset,pending}
}

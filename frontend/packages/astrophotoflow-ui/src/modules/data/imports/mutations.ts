import { useMutation, useQueryClient } from '@tanstack/vue-query'

import { importApi } from '../api'
import { importTasksKey } from './queries'
import { libraryQueryKey } from '../library/queries'

export function useSubmitImport() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn:({body}:{workspaceId:string;body:Parameters<typeof importApi.submit>[0]})=>importApi.submit(body),
    retry:false,
    onSettled:(_data,_error,{workspaceId})=>Promise.all([
      cache.invalidateQueries({queryKey:importTasksKey(workspaceId)}),
      cache.invalidateQueries({queryKey:libraryQueryKey(workspaceId)})
    ])
  })
}

export function useResumeImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ taskId }: { workspaceId: string; taskId: string }) => importApi.resume(taskId),
    // Re-read an uncertain response as well; never replay a resume automatically.
    onSettled: (_data, _error, { workspaceId }) =>
      queryClient.invalidateQueries({ queryKey: importTasksKey(workspaceId) })
  })
}

export function useRetryImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({taskId,body}: {workspaceId: string; taskId: string; body: Parameters<typeof importApi.retry>[1]}) => importApi.retry(taskId,body),
    retry: false,
    onSettled: (_data,_error,{workspaceId}) => queryClient.invalidateQueries({queryKey:importTasksKey(workspaceId)})
  })
}

/** The OS chooser is an explicit interaction, never a cached/background query. */
export function useSelectLocalFiles() {
  return useMutation({
    mutationFn: ({mode,signal}: {mode:Parameters<typeof importApi.select>[0]['mode'];signal:AbortSignal}) => importApi.select({mode},signal),
    retry: false
  })
}

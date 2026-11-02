import type { ConfigSave, ConfigState, WorkbenchResult } from './contracts'
import { createPlatformClient } from './api/client'
import type { FetchApi } from './api/client'
import {
  getWorkspaceLocaleApiV1SettingsLocaleGet,
  getWorkbenchConfigurationApiV1SettingsWorkbenchGet,
  saveWorkbenchConfigurationApiV1SettingsWorkbenchPatch,
  selectWorkbenchDirectoryApiV1SettingsWorkbenchSelectDirectoryPost,
  restartWorkbenchApiV1SettingsWorkbenchRestartPost,
  getWorkbenchRestartApiV1SettingsWorkbenchRestartOperationIdGet
} from '../generated/api/sdk.gen'

export { ApiClientError } from './api/errors'
export { createPlatformClient } from './api/client'
export type { FetchApi, PlatformClient, PlatformClientOptions } from './api/client'

export async function getWorkspaceLocale(fetchApi: FetchApi) {
  const { data } = await getWorkspaceLocaleApiV1SettingsLocaleGet<true>({
    client: createPlatformClient({ fetchApi }), throwOnError: true
  })
  return data
}

export interface WorkbenchClient {
  selectDirectory(path: string, signal?: AbortSignal): Promise<string | null>
  getConfiguration(signal?: AbortSignal): Promise<ConfigState>
  saveConfiguration(body: ConfigSave): Promise<ConfigState>
  restart(operationId: string): Promise<WorkbenchResult>
  restartResult(operationId: string, signal?: AbortSignal): Promise<WorkbenchResult | null>
}

export function createWorkbenchClient(fetchApi: FetchApi): WorkbenchClient {
  const options = { client: createPlatformClient({ fetchApi }), throwOnError: true } as const
  return {
    selectDirectory: async (path, signal) => {
      const { data } = await selectWorkbenchDirectoryApiV1SettingsWorkbenchSelectDirectoryPost<true>({ ...options, body: { path }, signal })
      return data.path
    },
    getConfiguration: async (signal) => (await getWorkbenchConfigurationApiV1SettingsWorkbenchGet<true>({...options,signal})).data,
    saveConfiguration: async (body) => (await saveWorkbenchConfigurationApiV1SettingsWorkbenchPatch<true>({ ...options, body })).data,
    restart: async (operationId) => (await restartWorkbenchApiV1SettingsWorkbenchRestartPost<true>({ ...options, body: { operation_id: operationId } })).data,
    restartResult: async (operationId, signal) => (await getWorkbenchRestartApiV1SettingsWorkbenchRestartOperationIdGet<true>({ ...options, path: { operation_id: operationId }, signal })).data
  }
}

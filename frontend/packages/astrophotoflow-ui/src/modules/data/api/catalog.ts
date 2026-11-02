import { getServiceHealth } from '../../../generated/api/sdk.gen'
import { listPresetsApiV1CapturePresetsGet } from '../../../generated/api/sdk.gen'
import type { ListPresetsApiV1CapturePresetsGetData } from '../../../generated/api/types.gen'
import { listSetupPresetsApiV1EquipmentSetupsSetupIdPresetsGet } from '../../../generated/api/sdk.gen'
import type { ListSetupPresetsApiV1EquipmentSetupsSetupIdPresetsGetData } from '../../../generated/api/types.gen'
import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import {
  getServiceCapabilities,
  listProjectsApiV1ProjectsGet,
  listEquipmentApiV1EquipmentGet,
  listSetupsApiV1EquipmentSetupsGet,
  listDatasetsApiV1DatasetsGet,
  listLibraryAssets,
  listProjectAssetsApiV1ProjectsProjectIdAssetsGet,
  listProjectDatasetsApiV1ProjectsProjectIdDatasetsGet
} from '../../../generated/api/sdk.gen'
import type {
  ListProjectsApiV1ProjectsGetData,
  ListEquipmentApiV1EquipmentGetData,
  ListSetupsApiV1EquipmentSetupsGetData,
  ListDatasetsApiV1DatasetsGetData,
  ListLibraryAssetsData,
  ListProjectAssetsApiV1ProjectsProjectIdAssetsGetData,
  ListProjectDatasetsApiV1ProjectsProjectIdDatasetsGetData
} from '../../../generated/api/types.gen'

export function nonEmptyQuery(values: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(values).filter(
      ([, value]) => value !== '' && value !== undefined
    )
  )
}

export function createCatalogClient(fetchApi: FetchApi) {
  const options = {
    client: createPlatformClient({ fetchApi }),
    throwOnError: true
  } as const
  return {
    health:async(signal?:AbortSignal)=>(await getServiceHealth<true>({...options,signal})).data,
    allPresets:async(query:NonNullable<ListPresetsApiV1CapturePresetsGetData['query']>,signal?:AbortSignal)=>(await listPresetsApiV1CapturePresetsGet<true>({...options,query,signal})).data,
    presets: async (
      setupId: string,
      query: NonNullable<
        ListSetupPresetsApiV1EquipmentSetupsSetupIdPresetsGetData['query']
      >,
      signal?: AbortSignal
    ) =>
      (
        await listSetupPresetsApiV1EquipmentSetupsSetupIdPresetsGet<true>({
          ...options,
          path: { setup_id: setupId },
          query,
          signal
        })
      ).data,
    capabilities: async (signal?: AbortSignal) =>
      (await getServiceCapabilities<true>({ ...options, signal })).data,
    projects: async (
      query: NonNullable<ListProjectsApiV1ProjectsGetData['query']>,
      signal?: AbortSignal
    ) =>
      (await listProjectsApiV1ProjectsGet<true>({ ...options, query, signal }))
        .data,
    equipment: async (
      query: NonNullable<ListEquipmentApiV1EquipmentGetData['query']>,
      signal?: AbortSignal
    ) =>
      (
        await listEquipmentApiV1EquipmentGet<true>({
          ...options,
          query,
          signal
        })
      ).data,
    setups: async (
      query: NonNullable<ListSetupsApiV1EquipmentSetupsGetData['query']>,
      signal?: AbortSignal
    ) =>
      (
        await listSetupsApiV1EquipmentSetupsGet<true>({
          ...options,
          query,
          signal
        })
      ).data,
    datasets: async (
      query: NonNullable<ListDatasetsApiV1DatasetsGetData['query']>,
      signal?: AbortSignal
    ) =>
      (await listDatasetsApiV1DatasetsGet<true>({ ...options, query, signal }))
        .data,
    assets: async (
      query: NonNullable<ListLibraryAssetsData['query']>,
      signal?: AbortSignal
    ) => (await listLibraryAssets<true>({ ...options, query, signal })).data,
    projectAssets: async (
      projectId: string,
      query: NonNullable<
        ListProjectAssetsApiV1ProjectsProjectIdAssetsGetData['query']
      >,
      signal?: AbortSignal
    ) =>
      (
        await listProjectAssetsApiV1ProjectsProjectIdAssetsGet<true>({
          ...options,
          path: { project_id: projectId },
          query,
          signal
        })
      ).data,
    projectDatasets: async (
      projectId: string,
      query: NonNullable<
        ListProjectDatasetsApiV1ProjectsProjectIdDatasetsGetData['query']
      >,
      signal?: AbortSignal
    ) =>
      (
        await listProjectDatasetsApiV1ProjectsProjectIdDatasetsGet<true>({
          ...options,
          path: { project_id: projectId },
          query,
          signal
        })
      ).data
  }
}

import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import {
  getSoftwarePackagesApiV1SoftwarePackagesGet,
  getSoftwareReleasesApiV1SoftwarePackagesPackageIdReleasesGet,
  getSoftwareCommandsApiV1SoftwarePackagesPackageIdVersionsVersionCommandsGet,
  getSoftwarePackageApiV1SoftwarePackagesPackageIdGet,
  requestSoftwareInstallApiV1SoftwarePackagesPackageIdInstallPost,
  requestSoftwareUninstallApiV1SoftwarePackagesPackageIdUninstallPost,
  prepareSoftwarePackageApiV1SoftwarePackagesPackageIdPreparePost
} from '../../../generated/api/sdk.gen'
import type { RequestSoftwareUninstallApiV1SoftwarePackagesPackageIdUninstallPostData } from '../../../generated/api/types.gen'
import type {
  SoftwareReleaseListing,
  PendingSoftwareAction,
  SoftwareInstallRequest,
  SoftwarePackage,
  SoftwarePackageDetails,
  SoftwarePreparation,
  SirilCommand
} from './contracts'
export { ApiClientError } from '../../../core/api/errors'

export interface SoftwareClient {
  listReleases(packageId: string, signal?: AbortSignal): Promise<SoftwareReleaseListing>
  listPackages(signal?: AbortSignal): Promise<SoftwarePackage[]>
  listCommands(packageId: string, version: string, signal?: AbortSignal): Promise<SirilCommand[]>
  getPackage(
    packageId: string,
    operationId?: string,
    signal?: AbortSignal
  ): Promise<SoftwarePackageDetails>
  requestUninstall(
    packageId: string,
    body: RequestSoftwareUninstallApiV1SoftwarePackagesPackageIdUninstallPostData['body']
  ): Promise<PendingSoftwareAction>
  requestInstall(
    packageId: string,
    body: SoftwareInstallRequest
  ): Promise<PendingSoftwareAction>
  prepare(packageId: string): Promise<SoftwarePreparation>
}

export function createSoftwareClient(fetchApi: FetchApi): SoftwareClient {
  const options = {
    client: createPlatformClient({ fetchApi }),
    throwOnError: true
  } as const
  return {
    listPackages: async (signal) =>
      (await getSoftwarePackagesApiV1SoftwarePackagesGet<true>({...options,signal})).data,
    listReleases: async (packageId, signal) =>
      (
        await getSoftwareReleasesApiV1SoftwarePackagesPackageIdReleasesGet<true>(
          { ...options, path: { package_id: packageId }, signal }
        )
      ).data,
    listCommands: async (packageId, version, signal) =>
      (
        await getSoftwareCommandsApiV1SoftwarePackagesPackageIdVersionsVersionCommandsGet<true>(
          { ...options, path: { package_id: packageId, version }, signal }
        )
      ).data,
    getPackage: async (packageId, operationId, signal) =>
      (
        await getSoftwarePackageApiV1SoftwarePackagesPackageIdGet<true>({
          ...options,
          path: { package_id: packageId },
          query: operationId ? { operation_id: operationId } : {},
          signal
        })
      ).data,
    requestInstall: async (packageId, body) =>
      (
        await requestSoftwareInstallApiV1SoftwarePackagesPackageIdInstallPost<true>(
          { ...options, path: { package_id: packageId }, body }
        )
      ).data,
    requestUninstall: async (packageId, body) =>
      (
        await requestSoftwareUninstallApiV1SoftwarePackagesPackageIdUninstallPost<true>(
          { ...options, path: { package_id: packageId }, body }
        )
      ).data,
    prepare: async (packageId) =>
      (
        await prepareSoftwarePackageApiV1SoftwarePackagesPackageIdPreparePost<true>(
          { ...options, path: { package_id: packageId } }
        )
      ).data
  }
}

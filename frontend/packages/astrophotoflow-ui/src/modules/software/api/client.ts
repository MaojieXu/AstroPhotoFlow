import { createApiClient } from '../../../core/client'
import type { FetchApi } from '../../../core/client'
import {
  pendingSoftwareActionSchema,
  softwareInstallRequestSchema,
  softwarePackageDetailsSchema,
  softwarePackageSchema,
  softwarePreparationSchema,
  sirilCommandSchema
} from './contracts'
import type {
  PendingSoftwareAction,
  SoftwareInstallRequest,
  SoftwarePackage,
  SoftwarePackageDetails,
  SoftwarePreparation,
  SirilCommand
} from './contracts'

export { ApiClientError } from '../../../core/client'

export interface SoftwareClient {
  listPackages(): Promise<SoftwarePackage[]>
  listCommands(packageId: string, version: string): Promise<SirilCommand[]>
  getPackage(
    packageId: string,
    operationId?: string
  ): Promise<SoftwarePackageDetails>
  requestUninstall(packageId: string, body: { package_token: string }): Promise<PendingSoftwareAction>
  requestInstall(
    packageId: string,
    body: SoftwareInstallRequest
  ): Promise<PendingSoftwareAction>
  prepare(packageId: string): Promise<SoftwarePreparation>
}

const basePath = '/astrophotoflow/api/v1/software/packages'

export function createSoftwareClient(fetchApi: FetchApi): SoftwareClient {
  const api = createApiClient(fetchApi)
  return {
    listPackages: () => api.get(basePath, softwarePackageSchema.array()),
    listCommands: (packageId, version) =>
      api.get(
        `${basePath}/${encodeURIComponent(packageId)}/versions/${encodeURIComponent(version)}/commands`,
        sirilCommandSchema.array()
      ),
    getPackage: (packageId, operationId) => {
      const query = operationId
        ? `?operation_id=${encodeURIComponent(operationId)}`
        : ''
      return api.get(
        `${basePath}/${encodeURIComponent(packageId)}${query}`,
        softwarePackageDetailsSchema
      )
    },
    requestInstall: (packageId, body) =>
      api.send(
        `${basePath}/${encodeURIComponent(packageId)}/install`,
        pendingSoftwareActionSchema,
        'POST',
        softwareInstallRequestSchema.parse(body)
      ),
    requestUninstall: (packageId, body) =>
      api.send(`${basePath}/${encodeURIComponent(packageId)}/uninstall`, pendingSoftwareActionSchema, 'POST', body),
    prepare: (packageId) =>
      api.send(
        `${basePath}/${encodeURIComponent(packageId)}/prepare`,
        softwarePreparationSchema,
        'POST',
        {}
      )
  }
}

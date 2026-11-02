import type { PendingSoftwareAction } from '../../../generated/api/types.gen'

export {
  zSoftwarePackage as softwarePackageSchema,
  zPendingSoftwareAction as pendingSoftwareActionSchema,
  zSoftwarePackageDetails as softwarePackageDetailsSchema,
  zSoftwarePreparation as softwarePreparationSchema,
  zSoftwareCommand as softwareCommandSchema,
  zSoftwareInstallRequest as softwareInstallRequestSchema,
  zSoftwareRelease as softwareReleaseSchema,
  zSoftwareReleaseListing as softwareReleaseListingSchema
} from '../../../generated/api/zod.gen'
export type {
  SoftwarePackage,
  PendingSoftwareAction,
  SoftwarePackageDetails,
  SoftwarePreparation,
  SoftwareCommand,
  SoftwareInstallRequest,
  SoftwareRelease,
  SoftwareReleaseListing
} from '../../../generated/api/types.gen'

// This is the UI confirmation outcome, not another HTTP DTO.
export type SoftwareConfirmationResult =
  | { ok: true; pending: PendingSoftwareAction }
  | { ok: false; code: string; message: string | null }

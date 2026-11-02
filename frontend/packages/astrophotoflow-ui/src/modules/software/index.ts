export { default as SoftwarePanel } from './SoftwarePanel.vue'
export { createSoftwareClient } from './api/client'
export { pendingSoftwareActionSchema } from './api/contracts'
export type { SoftwareClient } from './api/client'
export type {
  PendingSoftwareAction,
  SoftwareConfirmationResult,
  SoftwareInstallRequest,
  SoftwarePackage,
  SoftwarePackageDetails,
  SoftwarePreparation,
  SoftwareRelease,
  SoftwareReleaseListing,
  SoftwareCommand
} from './api/contracts'

export { useSoftwareWorkspace } from './queries'

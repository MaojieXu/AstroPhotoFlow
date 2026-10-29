export { Workspace } from './modules/data'
export { canvasDataRequestSchema, canvasDataSchema, canvasInspectSchema, scienceReferenceSchema, createCanvasDataClient } from './modules/data/api/canvas'
export type { CanvasData, CanvasDataRequest, CanvasInspect, ScienceReference } from './modules/data/api/canvas'
export type { LibraryControls } from './modules/data/workspace/libraryControls'
export { createMediaClient, mediaStateSchema, mediaSelectionSchema } from './modules/data/api/media'
export type { MediaState, MediaSelection, MediaMember, MediaViewerRequest } from './modules/data/api/media'
export { default as WorkbenchSettings } from './core/WorkbenchSettings.vue'
export { createWorkbenchClient } from './core/client'
export type { WorkbenchClient } from './core/client'
export type { ConfigSave, ConfigState, ConfigValues } from './core/contracts'
export { SoftwarePanel, createSoftwareClient, pendingSoftwareActionSchema } from './modules/software'
export { createSirilPreviewClient } from './modules/software/api/preview'
export type { SirilPreviewRequest } from './modules/software/api/preview'
export type {
  PendingSoftwareAction,
  SoftwareClient,
  SoftwareConfirmationResult,
  SoftwareInstallRequest,
  SoftwarePackage,
  SoftwarePackageDetails,
  SoftwarePreparation,
  SirilCommand
} from './modules/software'

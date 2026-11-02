import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter, Ref } from 'vue'
import type { ApiClientError } from '../api/client'
import type { SettingsProjectMode } from '../library/SettingsPage.vue'
import { libraryError as presentError } from '../library/errors'
import { useProjectReferences } from './mutations'
import {
  isAssetRecord,
  isDatasetRecord,
  isProjectAssetReference,
  isProjectDatasetReference,
  recordVersion,
  recordEntity
} from '../workspace/recordTypes'
import type { WorkspaceRecord } from '../workspace/recordTypes'

interface ProjectReferenceOptions {
  workspaceId: MaybeRefOrGetter<string>
  projectId: Ref<string | null>
  revision: Ref<number | null>
  selected: Ref<WorkspaceRecord | undefined>
  mode: MaybeRefOrGetter<SettingsProjectMode | undefined>
  choosing: MaybeRefOrGetter<boolean>
  error: Ref<ApiClientError | undefined>
  onAdded: (kind: 'asset' | 'dataset') => void
}

export function useProjectReferenceActions(options: ProjectReferenceOptions) {
  const workspaceId = computed(() => toValue(options.workspaceId))
  const mode = computed(() => toValue(options.mode))
  const choosing = computed(() => toValue(options.choosing))
  const {
    projectId: activeProjectId,
    revision: activeRevision,
    selected,
    error
  } = options
  const projectReferences = useProjectReferences()
  function projectReferenceContext() {
    const projectId = activeProjectId.value,
      revision = activeRevision.value,
      row = selected.value
    if (
      !projectId ||
      revision == null ||
      !row ||
      projectReferences.pending.value
    )
      return
    return {
      workspaceId: workspaceId.value,
      projectId,
      revision,
      row,
      mode: mode.value,
      choosing: choosing.value
    }
  }
  function currentProjectReference(
    target: NonNullable<ReturnType<typeof projectReferenceContext>>
  ) {
    return (
      workspaceId.value === target.workspaceId &&
      activeProjectId.value === target.projectId &&
      selected.value?.id === target.row.id &&
      mode.value === target.mode &&
      choosing.value === target.choosing
    )
  }
  function acknowledgeProjectRevision(
    target: NonNullable<ReturnType<typeof projectReferenceContext>>,
    revision: number
  ) {
    if (
      workspaceId.value === target.workspaceId &&
      activeProjectId.value === target.projectId &&
      activeRevision.value === target.revision
    )
      activeRevision.value = revision
  }
  async function addSelectedAsset() {
    const target = projectReferenceContext()
    const versionId =
      target && isAssetRecord(target.row)
        ? recordVersion(target.row)?.id
        : undefined
    if (!target || !versionId) return
    error.value = undefined
    try {
      await projectReferences.addAsset.mutateAsync({
        workspaceId: target.workspaceId,
        projectId: target.projectId,
        body: { base_revision: target.revision, asset_version_id: versionId }
      })
      acknowledgeProjectRevision(target, target.revision + 1)
      if (!currentProjectReference(target)) return
      options.onAdded('asset')
    } catch (cause) {
      if (currentProjectReference(target)) error.value = presentError(cause)
    }
  }
  async function removeSelectedAssetReference() {
    const target = projectReferenceContext()
    if (!target || !isProjectAssetReference(target.row)) return
    error.value = undefined
    try {
      const result = await projectReferences.removeAsset.mutateAsync({
        workspaceId: target.workspaceId,
        projectId: target.projectId,
        referenceId: target.row.id,
        body: { base_revision: target.revision }
      })
      acknowledgeProjectRevision(target, result.revision)
    } catch (cause) {
      if (currentProjectReference(target)) error.value = presentError(cause)
    }
  }
  async function addSelectedDataset() {
    const target = projectReferenceContext()
    const versionId =
      target && isDatasetRecord(target.row)
        ? recordVersion(target.row)?.id
        : undefined
    if (!target || !versionId) return
    error.value = undefined
    try {
      await projectReferences.addDataset.mutateAsync({
        workspaceId: target.workspaceId,
        projectId: target.projectId,
        body: {
          base_revision: target.revision,
          dataset_id: recordEntity(target.row).id,
          dataset_version_id: versionId
        }
      })
      acknowledgeProjectRevision(target, target.revision + 1)
      if (!currentProjectReference(target)) return
      options.onAdded('dataset')
    } catch (cause) {
      if (currentProjectReference(target)) error.value = presentError(cause)
    }
  }
  async function removeSelectedDatasetReference() {
    const target = projectReferenceContext()
    if (!target || !isProjectDatasetReference(target.row)) return
    error.value = undefined
    try {
      const result = await projectReferences.removeDataset.mutateAsync({
        workspaceId: target.workspaceId,
        projectId: target.projectId,
        referenceId: target.row.id,
        body: { base_revision: target.revision }
      })
      acknowledgeProjectRevision(target, result.revision)
    } catch (cause) {
      if (currentProjectReference(target)) error.value = presentError(cause)
    }
  }

  return {
    pending: projectReferences.pending,
    addSelectedAsset,
    removeSelectedAssetReference,
    addSelectedDataset,
    removeSelectedDatasetReference
  }
}

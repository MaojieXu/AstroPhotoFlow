import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter, Ref } from 'vue'
import type {
  AssetParametersPatch,
  DatasetMemberParametersUpdate
} from '../../../generated/api/types.gen'
import {
  zAssetParametersPatch,
  zAssetClassification,
  zPatchProjectApiV1ProjectsProjectIdPatchBody,
  zPatchDatasetApiV1DatasetsDatasetIdPatchBody
} from '../../../generated/api/zod.gen'
import { validatedInput } from '../../../core/api/input'
import { uiT } from '../../../core/i18n'
import { ApiClientError } from '../api/client'
import { useAssetEditor } from '../assets/useAssetEditor'
import { useEquipmentEditor } from '../equipment/useEquipmentEditor'
import { useUpdateProject } from '../projects/mutations'
import {
  useSaveDatasetDescription,
  useUpdateDatasetMembers
} from '../datasets/mutations'
import type { ParameterBinding } from './tableTypes'
import type { useInlineSaveState } from './useInlineSaveState'
import type { WorkspaceRecord, AssetRecord } from '../workspace/recordTypes'
import {
  assetRecord,
  datasetRecord,
  recordEntity,
  recordVersion,
  isAssetRecord,
  isDatasetRecord,
  isProjectRecord,
  isEquipmentRecord,
  acknowledgeAsset,
  acknowledgeDataset
} from '../workspace/recordTypes'

interface FieldEditingOptions {
  workspaceId: MaybeRefOrGetter<string>
  contextKey: () => string | undefined
  records: Ref<WorkspaceRecord[]>
  selected: Ref<WorkspaceRecord | undefined>
  editorSource: MaybeRefOrGetter<WorkspaceRecord | undefined>
  synchronizeDraft: (id: string, updated: unknown) => void
  datasetOpen: MaybeRefOrGetter<boolean>
  projectSaved: (id: string, revision: number) => void
  saveState: ReturnType<typeof useInlineSaveState>
}

export function useRecordFieldEditing(options: FieldEditingOptions) {
  const workspaceId = computed(() => toValue(options.workspaceId))
  const datasetOpen = computed(() => toValue(options.datasetOpen))
  const { selected, records: rows } = options
  const {
    beginInlineSave,
    finishInlineSave,
    setInlineSaveFailure,
    clearInlineSaveFailure
  } = options.saveState
  const assetEditor = useAssetEditor(workspaceId)
  const equipmentEditor = useEquipmentEditor(workspaceId)
  const projectWrite = useUpdateProject()
  const datasetWrite = useSaveDatasetDescription()
  const memberWrite = useUpdateDatasetMembers()
  async function saveInlineField(
    rowOrField: WorkspaceRecord | string,
    fieldOrValue: string | number | null,
    nextValue?: string | number | null
  ) {
    const row = typeof rowOrField === 'string' ? selected.value : rowOrField
    const field =
      typeof rowOrField === 'string' ? rowOrField : String(fieldOrValue)
    let value = typeof rowOrField === 'string' ? fieldOrValue : nextValue
    if (!row) return
    const origin = options.contextKey()
    const failureKey = inlineFailureKey(row, field)
    if (field === 'parameter_mode' && value === '')
      value = assetRecord(row) || isDatasetRecord(row) ? 'standard' : null
    if (value === '' && field !== 'name') value = null
    beginInlineSave()
    clearInlineSaveFailure(failureKey)
    try {
      await performInlineFieldSave(row, field, value ?? null)
    } catch (cause) {
      if (origin === options.contextKey())
        setInlineSaveFailure(
          failureKey,
          cause instanceof Error
            ? cause.message
            : uiT('apfUi.could_not_save_the_field')
        )
      throw cause
    } finally {
      finishInlineSave()
    }
  }

  function syncEditingDraft(row: WorkspaceRecord, updated: unknown) {
    options.synchronizeDraft(row.id, updated)
  }

  function editorRow() {
    return toValue(options.editorSource)
  }

  async function saveEditorInline(
    field: string,
    value: string | number | null
  ) {
    const row = editorRow()
    if (!row)
      throw new Error(uiT('apfUi.the_record_being_edited_no_longer_exists'))
    await saveInlineField(row, field, value)
  }

  function acknowledgeRecords(
    replace: (item: WorkspaceRecord) => WorkspaceRecord
  ) {
    rows.value = rows.value.map(replace)
    if (selected.value) selected.value = replace(selected.value)
  }
  function acceptAssetUpdate(
    row: AssetRecord,
    updated: import('../../../generated/api/types.gen').AssetOut
  ) {
    acknowledgeRecords((item) =>
      isAssetRecord(item) && recordEntity(item).id === updated.id
        ? acknowledgeAsset(item, updated)
        : item
    )
    syncEditingDraft(row, updated)
  }
  async function performInlineFieldSave(
    row: WorkspaceRecord,
    field: string,
    value: string | number | null
  ) {
    const origin = options.contextKey()
    if (field === 'parameter_mode' && value === '')
      value = isAssetRecord(row) || isDatasetRecord(row) ? 'standard' : null
    if (value === '' && field !== 'name') value = null
    if (
      isDatasetRecord(row) &&
      [
        'camera_id',
        'optical_system_id',
        'filter_id',
        'parameter_mode',
        'iso',
        'gain',
        'offset',
        'exposure_seconds',
        'integration_seconds',
        'sensor_temperature_c',
        'cfa_pattern'
      ].includes(field)
    )
      return saveDatasetParameter(row, field, value)
    if (isDatasetRecord(row) && ['frame_class', 'frame_type'].includes(field))
      return saveDatasetClassification(row, field, value)
    if (isAssetRecord(row)) {
      const asset = recordEntity(row)
      const updated = await assetEditor.saveField(asset, field, value)
      if (origin === options.contextKey()) acceptAssetUpdate(row, updated)
    } else if (isDatasetRecord(row)) {
      const dataset = datasetRecord(row)
      const updated = await datasetWrite.mutateAsync({
        workspaceId: workspaceId.value,
        datasetId: dataset.id,
        body: validatedInput(zPatchDatasetApiV1DatasetsDatasetIdPatchBody, {
          base_revision: dataset.revision,
          [field]: value
        })
      })
      if (origin !== options.contextKey()) return
      acknowledgeRecords((item) =>
        isDatasetRecord(item) && datasetRecord(item).id === updated.id
          ? acknowledgeDataset(item, updated)
          : item
      )
      syncEditingDraft(row, updated)
    } else if (isProjectRecord(row)) {
      const updated = await projectWrite.mutateAsync({
        workspaceId: workspaceId.value,
        projectId: row.id,
        body: validatedInput(zPatchProjectApiV1ProjectsProjectIdPatchBody, {
          base_revision: row.revision,
          [field]: value
        })
      })
      if (origin !== options.contextKey()) return
      acknowledgeRecords((item) =>
        isProjectRecord(item) && item.id === updated.id ? updated : item
      )
      options.projectSaved(row.id, updated.revision)
      syncEditingDraft(row, updated)
    } else if (isEquipmentRecord(row)) {
      const updated = await equipmentEditor.saveField(row, field, value)
      if (origin !== options.contextKey()) return
      acknowledgeRecords((item) =>
        isEquipmentRecord(item) && item.id === updated.id ? updated : item
      )
      syncEditingDraft(row, updated)
    } else
      throw new ApiClientError(
        'This record has no inline editing operation',
        'contract'
      )
  }

  async function saveRowField(
    row: WorkspaceRecord,
    field: string,
    value: string | number | null
  ) {
    await saveInlineField(row, field, value)
  }

  async function saveDatasetParameter(
    row: WorkspaceRecord,
    field: string,
    value: string | number | null
  ) {
    return saveDatasetParameters(
      row,
      zAssetParametersPatch.parse({ [field]: value })
    )
  }

  async function saveDatasetClassification(
    row: WorkspaceRecord,
    field: string,
    value: string | number | null
  ) {
    return updateDatasetMembers(row, {
      classification: zAssetClassification.parse({
        [field]: value === '' ? null : value
      })
    })
  }

  async function saveDatasetParameters(
    row: WorkspaceRecord,
    parameters: AssetParametersPatch
  ) {
    return updateDatasetMembers(row, { parameters })
  }

  async function saveParameterGroup(
    row: WorkspaceRecord,
    parameters: Parameters<ParameterBinding['save']>[0]
  ) {
    const origin = options.contextKey()
    const failureKey = inlineFailureKey(row, 'parameter_mode')
    beginInlineSave()
    clearInlineSaveFailure(failureKey)
    try {
      const patch = zAssetParametersPatch.parse(parameters)
      if (isDatasetRecord(row)) return await saveDatasetParameters(row, patch)
      if (isAssetRecord(row)) {
        const asset = recordEntity(row)
        const updated = await assetEditor.saveParameters(asset, patch)
        if (origin === options.contextKey()) acceptAssetUpdate(row, updated)
        return
      }

      throw new Error(
        uiT('apfUi.capture_parameters_cannot_be_edited_for_this_record')
      )
    } catch (cause) {
      if (origin === options.contextKey())
        setInlineSaveFailure(
          failureKey,
          cause instanceof Error
            ? cause.message
            : uiT('apfUi.could_not_save_parameters')
        )
      throw cause
    } finally {
      finishInlineSave()
    }
  }

  async function updateDatasetMembers(
    row: WorkspaceRecord,
    changes: Pick<
      DatasetMemberParametersUpdate,
      'parameters' | 'classification'
    >
  ) {
    if (!isDatasetRecord(row))
      throw new ApiClientError('Dataset record required', 'contract')
    const dataset = datasetRecord(row),
      versionId = recordVersion(row)?.id
    if (!versionId || !row.member_count)
      throw new Error(uiT('apfUi.this_image_group_has_no_editable_members'))
    if (
      !datasetOpen.value &&
      'matching_member_count' in row &&
      row.matching_member_count < row.member_count
    )
      throw new Error(
        uiT(
          'apfUi.these_results_include_group_members_with_other_frame_uses_or_propertie'
        )
      )
    await memberWrite.mutateAsync({
      workspaceId: workspaceId.value,
      datasetId: dataset.id,
      versionId,
      revision: dataset.revision,
      changes
    })
  }

  function inlineFailureKey(row: WorkspaceRecord | undefined, field: string) {
    return (row?.id ?? 'unknown') + ':' + field
  }
  function editorInlineFailureKey(field: string) {
    return inlineFailureKey(editorRow(), field)
  }
  async function saveBin(row: WorkspaceRecord, value: string | number | null) {
    const origin = options.contextKey()
    const failureKey = inlineFailureKey(row, 'binning')
    beginInlineSave()
    clearInlineSaveFailure(failureKey)
    try {
      await performBinSave(row, value)
    } catch (cause) {
      if (origin === options.contextKey())
        setInlineSaveFailure(
          failureKey,
          cause instanceof Error
            ? cause.message
            : uiT('apfUi.could_not_save_binning')
        )
      throw cause
    } finally {
      finishInlineSave()
    }
  }
  async function performBinSave(
    row: WorkspaceRecord,
    value: string | number | null
  ) {
    const origin = options.contextKey()
    const number =
      value == null || value === ''
        ? null
        : Number(String(value).replace(/^Bin/i, ''))
    if (
      number !== null &&
      (!Number.isInteger(number) || number < 1 || number > 16)
    )
      throw new Error(uiT('apfUi.binning_must_be_between_bin1_and_bin16'))
    if (isAssetRecord(row)) {
      const asset = recordEntity(row)
      const updated = await assetEditor.saveParameters(asset, {
        binning_x: number,
        binning_y: number
      })
      if (origin === options.contextKey()) acceptAssetUpdate(row, updated)
    } else if (isDatasetRecord(row))
      await saveDatasetParameters(row, { binning_x: number, binning_y: number })
  }

  return {
    saveEditorInline,
    saveRowField,
    saveParameterGroup,
    inlineFailureKey,
    editorInlineFailureKey,
    saveBin
  }
}

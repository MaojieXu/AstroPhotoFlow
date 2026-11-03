import { uiT } from '../../../core/i18n'
import { formatExposureSummary } from './exposurePresentation'
import type {
  AssetRecord,
  DatasetRecord,
  WorkspaceRecord
} from '../workspace/recordTypes'
import {
  assetRecord,
  datasetRecord,
  recordEntity,
  recordIssue,
  isDatasetRecord
} from '../workspace/recordTypes'
import { hasSummary } from './summary'
import { displayLabel } from './presentation'
import { cfaLabel, cfaChoices } from '../equipment/fields'
import { binValue, binEditValue, binEditChoices } from '../assets/binning'
import {
  rowParameters,
  rowClassification,
  datasetBinValue,
  datasetBinDisplay,
  datasetBinChoices,
  datasetFieldValue,
  parameterModeValue,
  parameterModeDisplay,
  displayTemperature,
  datasetTemperature,
  captureValue,
  frameClassLabel,
  frameTypeLabel,
  datasetFieldDisplay
} from './metadataPresentation'
import type {
  LibraryTableRow,
  InlineBinding,
  ParameterBinding
} from './tableTypes'
import type { useRecordFieldEditing } from './useRecordFieldEditing'

interface EquipmentDisplay {
  name: (
    row: WorkspaceRecord,
    key: 'camera_id' | 'optical_system_id' | 'filter_id'
  ) => string
  choices: (kind: string) => NonNullable<InlineBinding['choices']>
  message: (kind: string) => string | undefined
}
type RowEditor = Pick<
  ReturnType<typeof useRecordFieldEditing>,
  'saveRowField' | 'saveParameterGroup' | 'saveBin'
> & {
  cancelField: (row: WorkspaceRecord, field: string) => void
}
type RowDisplay = Pick<
  LibraryTableRow,
  | 'key'
  | 'title'
  | 'subtitle'
  | 'selected'
  | 'source'
  | 'thumbnail'
  | 'readiness'
>

/** Builds display bindings; writes and query lifetimes remain with their capability owners. */
export function createLibraryTableRow(
  row: AssetRecord | DatasetRecord,
  display: RowDisplay,
  equipment: EquipmentDisplay,
  editor: RowEditor
): LibraryTableRow {
  const { saveRowField, saveParameterGroup, saveBin } = editor
  const {
    name: materialEquipmentName,
    choices: equipmentChoices,
    message: equipmentChoiceMessage
  } = equipment
  const frameTypes = ['light', 'bias', 'dark', 'flat', 'dark_flat']
  const frameClasses = ['subframe', 'masterframe', 'video']
  const asset = assetRecord(row),
    entity = recordEntity(row),
    issue = recordIssue(row)
  const version = 'asset' in row ? row.version : asset?.current_version
  const availability = hasSummary(row)
    ? row.summary.availability.value
    : version?.availability
  return {
    ...display,
    dataset: isDatasetRecord(row),
    video: rowClassification(row).frame_class === 'video',
    memberCount: isDatasetRecord(row) ? datasetRecord(row).member_count : 0,
    exposureSummary: isDatasetRecord(row) ? formatExposureSummary('exposure_summary' in row ? row.exposure_summary : datasetRecord(row).exposure_summary) : undefined,
    mixedUse:
      isDatasetRecord(row) && datasetFieldValue(row, 'frame_type') === 'mixed',
    parametersDisplay: parameterModeDisplay(row),
    parameterSource:
      uiT(
        'apfUi.parameter_mode_is_not_inferred_automatically_from_file_values'
      ) +
      ['iso', 'gain', 'offset']
        .filter((key) => asset?.value_sources?.[key])
        .map((key) => key + '：' + displayLabel(asset?.value_sources[key]))
        .join('\n'),
    issue: issue
      ? {
          label: issue.includes(uiT('apfUi.parse'))
            ? uiT('apfUi.parsing_failed')
            : uiT('apfUi.metadata_processing_issue'),
          availability: displayLabel(availability),
          text: issue.replace(
            uiT('apfUi.original_files_will_continue_to_be_ingested'),
            uiT(
              'apfUi.use_the_current_original_readiness_status_as_the_authority'
            )
          )
        }
      : undefined,
    storage: isDatasetRecord(row)
      ? datasetFieldDisplay(row, 'storage_mode', displayLabel)
      : displayLabel(version?.storage_mode),
    availability: issue
      ? uiT('apfUi.metadata_processing_issue')
      : displayLabel(availability),
    fields: {
      get name(): InlineBinding {
        return {
          value: display.title,
          title: display.title,
          save: (value) => saveRowField(row, 'name', value),
          onCancelled: () => editor.cancelField(row, 'name')
        }
      },
      get groupClass(): InlineBinding {
        return {
          value: datasetFieldValue(row, 'frame_class'),
          display: datasetFieldDisplay(row, 'frame_class', frameClassLabel),
          kind: 'select',
          choices: [
            { value: '', label: uiT('apfUi.not_specified') },
            { value: 'mixed', label: uiT('apfUi.mixed'), disabled: true },
            ...frameClasses.map((value) => ({
              value,
              label: frameClassLabel(value)
            }))
          ],
          save: (value) => saveRowField(row, 'frame_class', value),
          onCancelled: () => editor.cancelField(row, 'frame_class')
        }
      },
      get groupType(): InlineBinding {
        return {
          value: datasetFieldValue(row, 'frame_type'),
          display: datasetFieldDisplay(row, 'frame_type', frameTypeLabel),
          kind: 'select',
          choices: [
            { value: '', label: uiT('apfUi.not_specified') },
            { value: 'mixed', label: uiT('apfUi.mixed'), disabled: true },
            ...frameTypes.map((value) => ({
              value,
              label: frameTypeLabel(value)
            }))
          ],
          save: (value) => saveRowField(row, 'frame_type', value),
          onCancelled: () => editor.cancelField(row, 'frame_type')
        }
      },
      get assetClass(): InlineBinding {
        return {
          value: rowClassification(row).frame_class ?? '',
          display: frameClassLabel(rowClassification(row).frame_class),
          kind: 'select',
          choices: [
            { value: '', label: uiT('apfUi.not_specified') },
            { value: 'mixed', label: uiT('apfUi.mixed'), disabled: true },
            ...frameClasses.map((value) => ({
              value,
              label: frameClassLabel(value)
            }))
          ],
          save: (value) => saveRowField(row, 'frame_class', value),
          onCancelled: () => editor.cancelField(row, 'frame_class')
        }
      },
      get assetType(): InlineBinding {
        return {
          value: rowClassification(row).frame_type ?? '',
          display: frameTypeLabel(rowClassification(row).frame_type),
          kind: 'select',
          choices: [
            { value: '', label: uiT('apfUi.not_specified') },
            { value: 'mixed', label: uiT('apfUi.mixed'), disabled: true },
            ...frameTypes.map((value) => ({
              value,
              label: frameTypeLabel(value)
            }))
          ],
          save: (value) => saveRowField(row, 'frame_type', value),
          onCancelled: () => editor.cancelField(row, 'frame_type')
        }
      },
      get camera(): InlineBinding {
        return {
          value: isDatasetRecord(row)
            ? datasetFieldValue(row, 'camera_id')
            : rowParameters(row).camera_id,
          display: isDatasetRecord(row)
            ? materialEquipmentName(row, 'camera_id')
            : materialEquipmentName(row, 'camera_id'),
          editValue:
            isDatasetRecord(row) &&
            datasetFieldValue(row, 'camera_id') === 'mixed'
              ? ''
              : undefined,
          kind: 'select',
          choices: [
            { value: '', label: uiT('apfUi.not_specified') },
            { value: 'mixed', label: uiT('apfUi.mixed'), disabled: true },
            ...equipmentChoices('camera')
          ],
          choicesMessage: equipmentChoiceMessage('camera'),
          save: (value) => saveRowField(row, 'camera_id', value),
          onCancelled: () => editor.cancelField(row, 'camera_id')
        }
      },
      get parameters(): ParameterBinding {
        return {
          value: parameterModeValue(row),
          display: parameterModeDisplay(row),
          unsetMode: 'standard',
          save: (changes) => saveParameterGroup(row, changes),
          onCancelled: () => editor.cancelField(row, 'parameter_mode')
        }
      },
      get exposure(): InlineBinding {
        return {
          value: isDatasetRecord(row)
            ? datasetFieldValue(row, 'exposure_seconds')
            : rowParameters(row).exposure_seconds,
          display: isDatasetRecord(row)
            ? datasetFieldDisplay(row, 'exposure_seconds', (value) =>
                value == null
                  ? uiT('apfUi.not_specified')
                  : String(value) + ' s'
              )
            : captureValue(rowParameters(row).exposure_seconds) +
              (rowParameters(row).exposure_seconds == null ? '' : ' s'),
          editValue:
            isDatasetRecord(row) &&
            datasetFieldValue(row, 'exposure_seconds') === 'mixed'
              ? ''
              : undefined,
          kind: 'number',
          save: (value) => saveRowField(row, 'exposure_seconds', value),
          onCancelled: () => editor.cancelField(row, 'exposure_seconds')
        }
      },
      get temperature(): InlineBinding {
        return {
          value: isDatasetRecord(row)
            ? datasetFieldValue(row, 'sensor_temperature_c')
            : rowParameters(row).sensor_temperature_c,
          display: isDatasetRecord(row)
            ? datasetTemperature(row)
            : rowParameters(row).sensor_temperature_c == null
              ? uiT('apfUi.not_specified')
              : displayTemperature(rowParameters(row).sensor_temperature_c) +
                ' °C',
          editValue:
            isDatasetRecord(row) &&
            datasetFieldValue(row, 'sensor_temperature_c') === 'mixed'
              ? ''
              : undefined,
          kind: 'number',
          save: (value) => saveRowField(row, 'sensor_temperature_c', value),
          onCancelled: () => editor.cancelField(row, 'sensor_temperature_c')
        }
      },
      get binning(): InlineBinding {
        return {
          value: isDatasetRecord(row)
            ? datasetBinValue(row)
            : binEditValue(rowParameters(row)),
          display: isDatasetRecord(row)
            ? datasetBinDisplay(row)
            : (binValue(rowParameters(row)) ?? uiT('apfUi.not_specified')),
          kind: 'select',
          choices: isDatasetRecord(row)
            ? datasetBinChoices(row)
            : binEditChoices(rowParameters(row)),
          save: (value) => saveBin(row, value),
          onCancelled: () => editor.cancelField(row, 'binning')
        }
      },
      get cfa(): InlineBinding {
        return {
          value: isDatasetRecord(row)
            ? datasetFieldValue(row, 'cfa_pattern')
            : (rowParameters(row).cfa_pattern ?? ''),
          display: isDatasetRecord(row)
            ? datasetFieldDisplay(row, 'cfa_pattern', cfaLabel)
            : cfaLabel(rowParameters(row).cfa_pattern),
          kind: 'select',
          choices: isDatasetRecord(row)
            ? [
                ...cfaChoices,
                { value: 'mixed', label: uiT('apfUi.mixed'), disabled: true }
              ]
            : cfaChoices,
          save: (value) => saveRowField(row, 'cfa_pattern', value),
          onCancelled: () => editor.cancelField(row, 'cfa_pattern')
        }
      },
      get opticalSystem(): InlineBinding {
        return {
          value: isDatasetRecord(row)
            ? datasetFieldValue(row, 'optical_system_id')
            : rowParameters(row).optical_system_id,
          display: isDatasetRecord(row)
            ? materialEquipmentName(row, 'optical_system_id')
            : materialEquipmentName(row, 'optical_system_id'),
          editValue:
            isDatasetRecord(row) &&
            datasetFieldValue(row, 'optical_system_id') === 'mixed'
              ? ''
              : undefined,
          kind: 'select',
          choices: [
            { value: '', label: uiT('apfUi.not_specified') },
            { value: 'mixed', label: uiT('apfUi.mixed'), disabled: true },
            ...equipmentChoices('optical_system')
          ],
          choicesMessage: equipmentChoiceMessage('optical_system'),
          save: (value) => saveRowField(row, 'optical_system_id', value),
          onCancelled: () => editor.cancelField(row, 'optical_system_id')
        }
      },
      get filter(): InlineBinding {
        return {
          value: isDatasetRecord(row)
            ? datasetFieldValue(row, 'filter_id')
            : rowParameters(row).filter_id,
          display: isDatasetRecord(row)
            ? materialEquipmentName(row, 'filter_id')
            : materialEquipmentName(row, 'filter_id'),
          editValue:
            isDatasetRecord(row) &&
            datasetFieldValue(row, 'filter_id') === 'mixed'
              ? ''
              : undefined,
          kind: 'select',
          choices: [
            { value: '', label: uiT('apfUi.not_specified') },
            { value: 'mixed', label: uiT('apfUi.mixed'), disabled: true },
            ...equipmentChoices('filter')
          ],
          choicesMessage: equipmentChoiceMessage('filter'),
          save: (value) => saveRowField(row, 'filter_id', value),
          onCancelled: () => editor.cancelField(row, 'filter_id')
        }
      },
      get integration(): InlineBinding {
        return {
          value: isDatasetRecord(row)
            ? datasetFieldValue(row, 'integration_seconds')
            : rowParameters(row).integration_seconds,
          display: isDatasetRecord(row)
            ? datasetFieldDisplay(row, 'integration_seconds', (value) =>
                value == null
                  ? uiT('apfUi.not_specified')
                  : String(value) + ' s'
              )
            : captureValue(rowParameters(row).integration_seconds) +
              (rowParameters(row).integration_seconds == null ? '' : ' s'),
          editValue:
            isDatasetRecord(row) &&
            datasetFieldValue(row, 'integration_seconds') === 'mixed'
              ? ''
              : undefined,
          kind: 'number',
          save: (value) => saveRowField(row, 'integration_seconds', value),
          onCancelled: () => editor.cancelField(row, 'integration_seconds')
        }
      },
      get status(): InlineBinding {
        return {
          value: entity.status ?? 'active',
          display: displayLabel(entity.status ?? 'active'),
          kind: 'select',
          choices: [
            { value: 'active', label: uiT('apfUi.active') },
            { value: 'archived', label: uiT('apfUi.archive') }
          ],
          save: (value) => saveRowField(row, 'status', value),
          onCancelled: () => editor.cancelField(row, 'status')
        }
      },
      get notes(): InlineBinding {
        return {
          value: isDatasetRecord(row)
            ? (isDatasetRecord(row) ? datasetRecord(row) : undefined)?.notes
            : entity.notes,
          kind: 'textarea',
          save: (value) => saveRowField(row, 'notes', value),
          onCancelled: () => editor.cancelField(row, 'notes')
        }
      },
      get opticalSystemReference(): InlineBinding {
        return {
          value: isDatasetRecord(row)
            ? datasetFieldValue(row, 'optical_system_id')
            : rowParameters(row).optical_system_id,
          display: isDatasetRecord(row)
            ? materialEquipmentName(row, 'optical_system_id')
            : materialEquipmentName(row, 'optical_system_id'),
          kind: 'select',
          choices: [
            { value: '', label: uiT('apfUi.not_specified') },
            { value: 'mixed', label: uiT('apfUi.mixed'), disabled: true },
            ...equipmentChoices('optical_system')
          ],
          choicesMessage: equipmentChoiceMessage('optical_system'),
          save: (value) => saveRowField(row, 'optical_system_id', value),
          onCancelled: () => editor.cancelField(row, 'optical_system_id')
        }
      },
      get filterReference(): InlineBinding {
        return {
          value: isDatasetRecord(row)
            ? datasetFieldValue(row, 'filter_id')
            : rowParameters(row).filter_id,
          display: isDatasetRecord(row)
            ? materialEquipmentName(row, 'filter_id')
            : materialEquipmentName(row, 'filter_id'),
          kind: 'select',
          choices: [
            { value: '', label: uiT('apfUi.not_specified') },
            { value: 'mixed', label: uiT('apfUi.mixed'), disabled: true },
            ...equipmentChoices('filter')
          ],
          choicesMessage: equipmentChoiceMessage('filter'),
          save: (value) => saveRowField(row, 'filter_id', value),
          onCancelled: () => editor.cancelField(row, 'filter_id')
        }
      },
      get statusReference(): InlineBinding {
        return {
          value: entity.status ?? 'active',
          display: displayLabel(entity.status ?? 'active'),
          kind: 'select',
          choices: [
            { value: 'active', label: uiT('apfUi.active') },
            { value: 'archived', label: uiT('apfUi.archive') }
          ],
          save: (value) => saveRowField(row, 'status', value),
          onCancelled: () => editor.cancelField(row, 'status')
        }
      },
      get notesReference(): InlineBinding {
        return {
          value: entity.notes,
          display: entity.notes ?? '—',
          kind: 'textarea',
          save: (value) => saveRowField(row, 'notes', value),
          onCancelled: () => editor.cancelField(row, 'notes')
        }
      }
    }
  }
}

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { workspaceQueryKey } from '../../../core/query/keys'
import { uiT } from '../../../core/i18n'
import { ApiClientError } from '../../../core/api/errors'
import { calibrationApi } from '../api/calibration'
import InlineField from '../components/InlineField.vue'
import { calibrationCellLabel, calibrationChoiceToken } from './inlineCalibration'
import { readPages } from './pagination'
import type { InlineCalibrationBinding } from './inlineCalibration'
import type { CalibrationPatch } from '../../../generated/api/types.gen'
type CalibrationChoice = NonNullable<CalibrationPatch['bias']>

const props = defineProps<{ binding: InlineCalibrationBinding }>()
const requested = ref(false)
const targets = useQuery({
  queryKey: computed(() => [...workspaceQueryKey(props.binding.context?.workspaceId ?? ''), 'calibration-master-choices', props.binding.slot]),
  enabled: computed(() => requested.value && Boolean(props.binding.context)),
  queryFn: ({ signal }) => readPages(offset => calibrationApi.search({slot:props.binding.slot, query:{target_kind:'master',limit:200,offset:offset ?? 0}}, signal), true, signal),
  staleTime: 30_000
})
const label = computed(() => calibrationCellLabel(props.binding.value))
const failureKey = computed(() => `calibration:${props.binding.context?.assetId}:${props.binding.slot}`)
const title = computed(() => {
  const value = props.binding.value, target = value.target_detail
  const source = uiT(value.source === 'dataset' ? 'apfUi.calibration_from_dataset' : 'apfUi.calibration_standalone')
  return [label.value, target ? target.target.id : '', source,
    !props.binding.context ? uiT('apfUi.calibration_open_group_hint') : ''].filter(Boolean).join('\n')
})
const choices = computed(() => {
  const result = [
    {value:'unconfigured',label:uiT('apfUi.calibration_unconfigured')},
    {value:'disabled',label:uiT('apfUi.calibration_disabled')},
    ...(targets.data.value?.items.map(item => ({value:item.target.id,label:item.name})) ?? [])
  ]
  const target = props.binding.value.target_detail
  if (target && !result.some(item => item.value === target.target.id)) result.push({value:target.target.id,label:target.name})
  return result
})
const save = computed(() => {
  const { context, slot } = props.binding
  const saveFailureKey = failureKey.value
  return async (value: string | number | null) => {
  if (!context) return
  const choice: CalibrationChoice = value === 'disabled' ? {mode:'disabled'}
    : value === 'unconfigured' ? {mode:'unconfigured'} : {mode:'target',target:{kind:'asset',id:String(value)}}
  const changes: CalibrationPatch = {[slot]:choice}
  const requestId = crypto.randomUUID()
  const submit = (acceptUnknown: boolean) => calibrationApi.updateImage(context.assetId,{
    request_id:requestId,expected_revision:context.revision,changes,accept_unknown:acceptUnknown})
  await context.runSave(saveFailureKey, async () => {
    try { await submit(false) }
    catch (cause) {
      if (!(cause instanceof ApiClientError) || cause.code !== 'CALIBRATION_UNKNOWN') throw cause
      const details = [...new Set(cause.fields?.map(field => field.message) ?? [cause.message])].join('\n')
      if (!window.confirm(uiT('apfUi.calibration_confirm_unknown',{details}))) throw cause
      await submit(true)
    }
    await context.saved()
  })
  }
})
</script>

<template>
  <span class="apf-calibration-cell" @focusin="requested = true" @dblclick.capture="requested = true">
    <InlineField v-if="binding.context" :value="calibrationChoiceToken(binding.value.choice)" :display="label" :title="title" kind="select" :choices="choices" :choices-message="targets.isFetching.value ? $t('apfUi.calibration_loading') : targets.error.value?.message" :save="save" @cancelled="binding.context?.cancel(failureKey)" />
    <span v-else :title="title">{{ label }}</span>
  </span>
</template>

<style scoped>
.apf-calibration-cell{display:block;min-width:100px;max-width:180px;white-space:nowrap;font-size:12px}
.apf-calibration-cell>span{display:block;overflow:hidden;text-overflow:ellipsis}
.apf-calibration-cell :deep(.apf-inline-field){width:100%;min-width:0}
.apf-calibration-cell :deep(.apf-inline-value){overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
</style>

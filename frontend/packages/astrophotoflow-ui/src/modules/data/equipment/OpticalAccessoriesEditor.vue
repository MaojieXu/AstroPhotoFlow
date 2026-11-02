<script setup lang="ts">
import { uiT } from '../../../core/i18n'
import type { TelescopeSpecs } from '../../../generated/api/types.gen'
import LibraryButton from '../components/LibraryButton.vue'
import LibraryInput from '../components/LibraryInput.vue'

type Accessories = NonNullable<TelescopeSpecs['optical_accessories']>
const accessories = defineModel<Accessories>({ required: true })
function validateFactor(event: Event) {
  const input = event.target
  if (!(input instanceof HTMLInputElement)) return
  const factor = Number(input.value)
  input.setCustomValidity(input.value !== '' && Number.isFinite(factor) && factor > 0 ? '' : uiT('apfUi.optical_accessory_factor_help'))
}
function add() {
  accessories.value = [...accessories.value, { id: crypto.randomUUID(), name: '', factor: 1 }]
}
function update(index: number, field: 'name' | 'factor', value: string | number | null | undefined) {
  accessories.value = accessories.value.map((item, position) => position === index
    ? { ...item, [field]: field === 'factor' ? Number(value) : String(value ?? '') }
    : item)
}
</script>

<template>
  <section class="apf-device-section apf-optical-accessories" :aria-label="$t('apfUi.telescope_accessories')">
    <div class="apf-accessory-heading">
      <h3>{{ $t('apfUi.telescope_accessories') }}</h3>
      <LibraryButton type="button" @click="add">{{ $t('apfUi.add_optical_accessory') }}</LibraryButton>
    </div>
    <p v-if="!accessories.length">{{ $t('apfUi.no_optical_accessories') }}</p>
    <div v-if="accessories.length" class="apf-accessory-columns" aria-hidden="true">
      <span>{{ $t('apfUi.accessory_name') }}</span><span>{{ $t('apfUi.accessory_factor') }}</span><span />
    </div>
    <div v-for="(item,index) in accessories" :key="item.id" class="apf-accessory-row">
      <LibraryInput :model-value="item.name" :aria-label="$t('apfUi.accessory_name')+' '+(index+1)" required pattern=".*\S.*" @update:model-value="update(index,'name',$event)" />
      <span class="apf-device-input-unit">
        <LibraryInput :model-value="item.factor" :aria-label="$t('apfUi.accessory_factor')+' '+(index+1)" type="number" min="0" step="any" required @input="validateFactor" @update:model-value="update(index,'factor',$event)" />
        <span class="apf-device-unit" aria-hidden="true">×</span>
      </span>
      <LibraryButton type="button" class="apf-accessory-remove" :aria-label="$t('apfUi.remove')+' '+item.name" :tooltip="$t('apfUi.remove')" @click="accessories=accessories.filter((_,position)=>position!==index)"><i class="icon-[lucide--x] size-4" aria-hidden="true" /></LibraryButton>
    </div>
    <p class="apf-device-help">{{ $t('apfUi.optical_accessory_factor_help') }}</p>
  </section>
</template>

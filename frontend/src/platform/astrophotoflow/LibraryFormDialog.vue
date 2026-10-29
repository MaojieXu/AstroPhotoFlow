<script setup lang="ts">
import { nextTick, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import Button from '@/components/ui/button/Button.vue'
import Dialog from '@/components/ui/dialog/Dialog.vue'
import DialogContent from '@/components/ui/dialog/DialogContent.vue'
import DialogHeader from '@/components/ui/dialog/DialogHeader.vue'
import DialogOverlay from '@/components/ui/dialog/DialogOverlay.vue'
import DialogPortal from '@/components/ui/dialog/DialogPortal.vue'
import DialogTitle from '@/components/ui/dialog/DialogTitle.vue'

const { open, title, label, busy = false } = defineProps<{
  open: boolean
  title: string
  label?: string
  busy?: boolean
}>()
const emit = defineEmits<{ close: [] }>()
const content = useTemplateRef<InstanceType<typeof DialogContent>>('content')
const { t } = useI18n()

watch(() => title, async () => {
  await nextTick()
  content.value?.$el.querySelector('[autofocus]')?.focus()
})

function requestClose() {
  if (!busy) emit('close')
}
</script>

<template>
  <Dialog :open @update:open="!$event && requestClose()">
    <DialogPortal>
      <DialogOverlay />
      <DialogContent ref="content" size="md" class="apf-equipment-dialog" :aria-label="label ?? title" :aria-describedby="undefined">
        <DialogHeader>
          <DialogTitle>{{ title }}</DialogTitle>
          <Button type="button" size="icon" variant="textonly" :aria-label="t('g.close')" :disabled="busy" @click="requestClose">
            <i class="icon-[lucide--x] size-4" aria-hidden="true" />
          </Button>
        </DialogHeader>
        <slot />
      </DialogContent>
    </DialogPortal>
  </Dialog>
</template>

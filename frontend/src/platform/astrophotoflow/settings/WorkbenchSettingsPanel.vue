<script setup lang="ts">
import { WorkbenchSettings, createWorkbenchClient } from '@astrophotoflow/ui'

import FormItem from '@/components/common/FormItem.vue'
import FormNumberField from '@/components/common/FormNumberField.vue'
import Button from '@/components/ui/button/Button.vue'
import Input from '@/components/ui/input/Input.vue'

const client = createWorkbenchClient((path, init) => fetch(path, init))
const controls = {
  formItem: FormItem,
  button: Button,
  input: Input,
  number: FormNumberField
}
</script>

<template>
  <WorkbenchSettings :client="client" :translate="$t" :controls="controls" />
</template>

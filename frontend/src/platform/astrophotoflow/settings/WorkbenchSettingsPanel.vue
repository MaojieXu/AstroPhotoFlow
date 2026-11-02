<script setup lang="ts">
import { WorkbenchSettings, createWorkbenchClient } from '@astrophotoflow/ui'

import FormItem from '@/components/common/FormItem.vue'
import Button from '@/components/ui/button/Button.vue'
import Input from '@/components/ui/input/Input.vue'

const client = createWorkbenchClient((path, init) => fetch(path, init))
const controls = { formItem: FormItem, button: Button, input: Input }
</script>

<template>
  <WorkbenchSettings :client="client" :translate="$t" :controls="controls" />
</template>

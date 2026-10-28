<script setup lang="ts">
import {
  computed,
  onMounted,
  onBeforeUnmount,
  ref,
  shallowRef,
  toRaw,
  watch
} from 'vue'

import type { Component } from 'vue'

import { ApiClientError } from './client'
import type { WorkbenchClient } from './client'
import type { ConfigSave, ConfigState, ConfigValues } from './contracts'

const { client, translate, controls } = defineProps<{
  client: WorkbenchClient
  controls: { formItem: Component; button: Component; input: Component }
  translate: (key: string) => string
}>()

const phase = ref<'loading' | 'ready' | 'saving' | 'restarting' | 'selecting'>(
  'loading'
)
const configuration = ref<ConfigState | null>(null)
const form = ref<ConfigValues | null>(null)
const defaultWorkspace = ref('')
const error = shallowRef<unknown>(null)
const saved = ref(false)
const hasUnsavedChanges = computed(() =>
  Boolean(
    configuration.value &&
    form.value &&
    (JSON.stringify(form.value) !== JSON.stringify(configuration.value.saved) ||
      defaultWorkspace.value !== (configuration.value.default_workspace ?? ''))
  )
)
watch(hasUnsavedChanges, (changed) => {
  if (changed) saved.value = false
})
const requestError = computed(() =>
  error.value instanceof ApiClientError ? error.value : null
)
const errorMessage = computed(() =>
  error.value instanceof Error
    ? error.value.message
    : translate('apfWorkbench.unexpectedError')
)
const serviceUrl = computed(() => {
  const effective = configuration.value?.effective
  if (!effective) return null
  const host = effective.host.includes(':')
    ? `[${effective.host}]`
    : effective.host
  return `http://${host}:${effective.service_port}`
})

const workspaceHint = computed(
  () => `${translate('apfWorkbench.defaultHelp')}\n\n${defaultWorkspace.value}`
)
const dataDirectoryHint = computed(() => {
  if (!configuration.value || !form.value) return ''
  const content = [
    translate('apfWorkbench.dataDirectoryHelp'),
    `${translate('apfWorkbench.absoluteDataDirectory')}: ${configuration.value.data_dir_absolute}`
  ]
  if (form.value.data_dir !== configuration.value.saved.data_dir) {
    content.push(
      `${translate('apfWorkbench.currentDataDirectory')}: ${form.value.data_dir}`
    )
  }
  return content.join('\n\n')
})

async function reload() {
  phase.value = 'loading'
  error.value = null
  saved.value = false
  try {
    const current = await client.getConfiguration()
    configuration.value = current
    form.value = structuredClone(current.saved)
    defaultWorkspace.value = current.default_workspace ?? ''
  } catch (cause) {
    error.value = cause
  } finally {
    phase.value = 'ready'
  }
}

async function save() {
  if (!configuration.value || !form.value) return
  const body: ConfigSave = {
    config_token: configuration.value.config_token,
    values: structuredClone(toRaw(form.value))
  }
  if (
    defaultWorkspace.value !== (configuration.value.default_workspace ?? '')
  ) {
    if (!defaultWorkspace.value.trim()) {
      error.value = new Error(translate('apfWorkbench.defaultRequired'))
      return
    }
    body.default_workspace = defaultWorkspace.value
  }
  phase.value = 'saving'
  error.value = null
  saved.value = false
  try {
    const current = await client.saveConfiguration(body)
    configuration.value = current
    form.value = structuredClone(current.saved)
    defaultWorkspace.value = current.default_workspace ?? ''
    saved.value = true
  } catch (cause) {
    error.value = cause
  } finally {
    phase.value = 'ready'
  }
}

async function chooseDirectory(target: 'default_workspace' | 'data_dir') {
  if (!form.value) return
  phase.value = 'selecting'
  error.value = null
  try {
    const selected = await client.selectDirectory(
      target === 'default_workspace'
        ? defaultWorkspace.value
        : form.value.data_dir
    )
    if (selected !== null) {
      if (target === 'default_workspace') defaultWorkspace.value = selected
      else form.value.data_dir = selected
      saved.value = false
    }
  } catch (cause) {
    error.value = cause
  } finally {
    phase.value = 'ready'
  }
}

const restartMessage = ref('')
const restartAddress = computed(
  () => configuration.value?.saved.allowed_origins[0]
)
const portChanges = computed(
  () =>
    restartAddress.value !== configuration.value?.effective?.allowed_origins[0]
)
let disposed = false
onBeforeUnmount(() => {
  disposed = true
})

async function restartWorkbench() {
  phase.value = 'restarting'
  error.value = null
  restartMessage.value = translate('apfWorkbench.restarting')
  const operationId = crypto.randomUUID()
  try {
    try {
      await client.restart(operationId)
    } catch (cause) {
      if (
        !(cause instanceof ApiClientError) ||
        (cause.kind !== 'network' && cause.status !== 503)
      )
        throw cause
    }
    const deadline = Date.now() + 300_000
    while (!disposed && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 1000))
      if (disposed) return
      try {
        const result = await client.restartResult(operationId)
        if (!result || result.state === 'in_progress') continue
        if (result.state !== 'completed') {
          throw new Error(
            [result.detail, ...result.blockers].filter(Boolean).join(' · ') ||
              translate('apfWorkbench.restartUnknown')
          )
        }
        await reload()
        restartMessage.value = translate('apfWorkbench.restarted')
        return
      } catch (cause) {
        if (
          cause instanceof ApiClientError &&
          (cause.kind === 'network' || cause.status === 503)
        )
          continue
        throw cause
      }
    }
    if (!disposed) throw new Error(translate('apfWorkbench.restartUnknown'))
  } catch (cause) {
    error.value = cause
    restartMessage.value = ''
  } finally {
    if (!disposed) phase.value = 'ready'
  }
}

onMounted(reload)
</script>

<template>
  <section
    class="space-y-6 text-sm text-base-foreground"
    data-testid="workbench-settings"
  >
    <header class="flex items-start justify-between gap-4">
      <div class="flex items-center gap-1">
        <h2 class="m-0 text-lg font-semibold">
          {{ translate('apfWorkbench.title') }}
        </h2>
        <component
          :is="controls.button"
          type="button"
          size="icon-sm"
          variant="muted-textonly"
          icon="icon-[lucide--info]"
          :tooltip="translate('apfWorkbench.saveHelp')"
          :aria-label="translate('apfWorkbench.configurationHelp')"
          @click.stop
        >
          <template #tooltip
            ><span class="block max-w-sm break-all whitespace-pre-line">{{
              translate('apfWorkbench.saveHelp')
            }}</span></template
          >
        </component>
      </div>
      <component
        :is="controls.button"
        type="button"
        variant="muted-textonly"
        :disabled="phase !== 'ready'"
        @click="reload"
      >
        {{ translate('apfWorkbench.reload') }}
      </component>
    </header>

    <div
      v-if="error"
      role="alert"
      class="rounded-md border border-destructive-background p-3 text-destructive-background"
    >
      <p class="m-0">{{ errorMessage }}</p>
      <p v-if="requestError?.status === 409" class="mb-0 text-sm">
        {{ translate('apfWorkbench.conflictHelp') }}
      </p>
      <ul v-if="requestError?.fields?.length" class="mb-0 text-sm">
        <li v-for="field in requestError.fields" :key="field.path">
          {{ field.path }}: {{ field.message }}
        </li>
      </ul>
      <p v-if="requestError?.requestId" class="mb-0 text-xs break-all">
        {{ translate('apfWorkbench.requestId') }}: {{ requestError.requestId }}
      </p>
    </div>
    <p v-if="phase === 'loading'" role="status">
      {{ translate('apfWorkbench.loading') }}
    </p>
    <p
      v-if="phase === 'selecting'"
      role="status"
      class="text-sm text-muted-foreground"
    >
      {{ translate('apfWorkbench.selectingDirectory') }}
    </p>
    <p
      v-if="configuration"
      class="m-0 flex items-center gap-2 text-sm"
      data-testid="configuration-state"
    >
      <i
        :class="
          configuration.restart_required
            ? 'icon-[lucide--clock-3]'
            : 'icon-[lucide--check]'
        "
        class="size-4 shrink-0"
        aria-hidden="true"
      />
      {{
        translate(
          configuration.restart_required
            ? 'apfWorkbench.restartRequired'
            : 'apfWorkbench.inSync'
        )
      }}
    </p>

    <form v-if="form && configuration" class="space-y-6" @submit.prevent="save">
      <fieldset
        :disabled="phase !== 'ready'"
        class="m-0 space-y-6 border-0 p-0"
      >
        <div class="space-y-4">
          <div>
            <component
              :is="controls.formItem"
              id="file_workers"
              v-model:form-value="form.file_workers"
              :item="{
                name: translate('apfWorkbench.fileWorkers'),
                type: 'number',
                tooltip: translate('apfWorkbench.fileWorkersHelp'),
                attrs: { min: 1, step: 1, name: 'file_workers' }
              }"
            />
            <p
              v-if="
                configuration.effective &&
                form.file_workers !== configuration.effective.file_workers
              "
              class="m-0 text-xs text-muted-foreground"
              data-testid="effective-file-workers"
            >
              {{ translate('apfWorkbench.effective') }}:
              {{ configuration.effective.file_workers }}
            </p>
          </div>
          <div>
            <component
              :is="controls.formItem"
              id="preview_workers"
              v-model:form-value="form.preview_workers"
              :item="{
                name: translate('apfWorkbench.previewWorkers'),
                type: 'number',
                tooltip: translate('apfWorkbench.previewWorkersHelp'),
                attrs: { min: 1, step: 1, name: 'preview_workers' }
              }"
            />
            <p
              v-if="
                configuration.effective &&
                form.preview_workers !== configuration.effective.preview_workers
              "
              class="m-0 text-xs text-muted-foreground"
            >
              {{ translate('apfWorkbench.effective') }}:
              {{ configuration.effective.preview_workers }}
            </p>
          </div>
        </div>

        <section class="border-t border-border-default pt-4">
          <div class="flex items-center gap-1">
            <h3 class="m-0 text-base font-medium">
              {{ translate('apfWorkbench.advanced') }}
            </h3>
            <component
              :is="controls.button"
              type="button"
              size="icon-sm"
              variant="muted-textonly"
              icon="icon-[lucide--info]"
              :tooltip="configuration.config_path"
              :aria-label="translate('apfWorkbench.configurationPath')"
              @click.stop
            >
              <template #tooltip
                ><span class="block max-w-sm break-all whitespace-pre-line">{{
                  configuration.config_path
                }}</span></template
              >
            </component>
          </div>
          <div class="mt-4 space-y-4">
            <div class="flex flex-wrap items-center gap-2">
              <component
                :is="controls.formItem"
                id="default_workspace"
                class="min-w-0 flex-1"
                v-model:form-value="defaultWorkspace"
                :item="{
                  name: translate('apfWorkbench.defaultWorkspace'),
                  type: 'text',
                  attrs: { name: 'default_workspace' }
                }"
              >
                <template #name-suffix>
                  <component
                    :is="controls.button"
                    type="button"
                    size="icon-sm"
                    variant="muted-textonly"
                    class="ml-1 align-middle"
                    icon="icon-[lucide--info]"
                    :tooltip="workspaceHint"
                    :aria-label="translate('apfWorkbench.workspaceHelp')"
                    @click.stop
                  >
                    <template #tooltip
                      ><span
                        class="block max-w-sm break-all whitespace-pre-line"
                        >{{ workspaceHint }}</span
                      ></template
                    >
                  </component>
                </template>
              </component>
              <component
                :is="controls.button"
                type="button"
                :aria-label="translate('apfWorkbench.chooseWorkspace')"
                @click="chooseDirectory('default_workspace')"
              >
                {{ translate('apfWorkbench.chooseDirectory') }}
              </component>
            </div>
            <component
              :is="controls.formItem"
              id="host"
              v-model:form-value="form.host"
              :item="{
                name: translate('apfWorkbench.host'),
                type: 'text',
                attrs: { name: 'host', required: true }
              }"
            />
            <component
              :is="controls.formItem"
              id="service_port"
              v-model:form-value="form.service_port"
              :item="{
                name: translate('apfWorkbench.servicePort'),
                type: 'number',
                attrs: { min: 1, max: 65535, step: 1, name: 'service_port' }
              }"
            />
            <div class="flex flex-wrap items-center gap-2">
              <component
                :is="controls.formItem"
                id="data_dir"
                class="min-w-0 flex-1"
                v-model:form-value="form.data_dir"
                :item="{
                  name: translate('apfWorkbench.dataDir'),
                  type: 'text',
                  attrs: { name: 'data_dir', required: true }
                }"
              >
                <template #name-suffix>
                  <component
                    :is="controls.button"
                    type="button"
                    size="icon-sm"
                    variant="muted-textonly"
                    class="ml-1 align-middle"
                    icon="icon-[lucide--info]"
                    :tooltip="dataDirectoryHint"
                    data-testid="data-directory-hint"
                    :aria-label="translate('apfWorkbench.dataDirectoryDetails')"
                    @click.stop
                  >
                    <template #tooltip
                      ><span
                        class="block max-w-sm break-all whitespace-pre-line"
                        >{{ dataDirectoryHint }}</span
                      ></template
                    >
                  </component>
                </template>
              </component>
              <component
                :is="controls.button"
                type="button"
                :aria-label="translate('apfWorkbench.chooseDataDirectory')"
                @click="chooseDirectory('data_dir')"
              >
                {{ translate('apfWorkbench.chooseDirectory') }}
              </component>
            </div>
            <div class="space-y-2">
              <p class="m-0 text-sm text-muted">
                {{ translate('apfWorkbench.origins') }}
              </p>
              <div
                v-for="(_, index) in form.allowed_origins"
                :key="index"
                class="flex items-center gap-2"
              >
                <component
                  :is="controls.input"
                  v-model="form.allowed_origins[index]"
                  :aria-label="translate('apfWorkbench.origins')"
                  required
                  class="min-w-0 flex-1"
                />
                <component
                  :is="controls.button"
                  type="button"
                  variant="muted-textonly"
                  @click="form.allowed_origins.splice(index, 1)"
                  >{{ translate('apfWorkbench.remove') }}</component
                >
              </div>
              <component
                :is="controls.button"
                type="button"
                @click="form.allowed_origins.push('')"
                >{{ translate('apfWorkbench.addOrigin') }}</component
              >
            </div>
            <div class="space-y-2">
              <p class="m-0 text-sm text-muted">
                {{ translate('apfWorkbench.importRoots') }}
              </p>
              <div
                v-for="(root, index) in form.import_roots"
                :key="index"
                class="flex flex-wrap items-center gap-2"
              >
                <component
                  :is="controls.input"
                  v-model="root.id"
                  :aria-label="translate('apfWorkbench.rootId')"
                  :placeholder="translate('apfWorkbench.rootId')"
                  required
                  class="min-w-0 flex-1"
                />
                <component
                  :is="controls.input"
                  v-model="root.path"
                  :aria-label="translate('apfWorkbench.rootPath')"
                  :placeholder="translate('apfWorkbench.rootPath')"
                  required
                  class="min-w-0 flex-1"
                />
                <component
                  :is="controls.button"
                  type="button"
                  size="icon-sm"
                  variant="muted-textonly"
                  icon="icon-[lucide--info]"
                  :tooltip="root.path"
                  :aria-label="translate('apfWorkbench.importRootDetails')"
                  @click.stop
                >
                  <template #tooltip
                    ><span
                      class="block max-w-sm break-all whitespace-pre-line"
                      >{{ root.path }}</span
                    ></template
                  >
                </component>
                <component
                  :is="controls.button"
                  type="button"
                  variant="muted-textonly"
                  @click="form.import_roots.splice(index, 1)"
                  >{{ translate('apfWorkbench.remove') }}</component
                >
              </div>
              <component
                :is="controls.button"
                type="button"
                @click="form.import_roots.push({ id: '', path: '' })"
                >{{ translate('apfWorkbench.addRoot') }}</component
              >
            </div>
          </div>
        </section>
      </fieldset>

      <p v-if="saved" role="status" class="m-0 text-sm">
        {{ translate('apfWorkbench.saved') }}
      </p>
      <div class="flex flex-wrap gap-2 border-t border-border-default pt-4">
        <component
          :is="controls.button"
          type="submit"
          variant="primary"
          :disabled="phase !== 'ready'"
        >
          {{
            translate(
              phase === 'saving' ? 'apfWorkbench.saving' : 'apfWorkbench.save'
            )
          }}
        </component>
        <component
          :is="controls.button"
          type="button"
          variant="secondary"
          :disabled="phase !== 'ready' || hasUnsavedChanges"
          data-testid="workbench-restart"
          :title="
            hasUnsavedChanges
              ? translate('apfWorkbench.saveFirst')
              : translate('apfWorkbench.restart')
          "
          @click="restartWorkbench"
        >
          <i class="icon-[lucide--rotate-cw] size-4" aria-hidden="true" />{{
            translate('apfWorkbench.restart')
          }}
        </component>
        <component
          :is="controls.button"
          type="button"
          size="icon-sm"
          variant="muted-textonly"
          class="self-center"
          icon="icon-[lucide--info]"
          :tooltip="translate('apfWorkbench.restartHelp')"
          :aria-label="translate('apfWorkbench.restartDetails')"
          @click.stop
        >
          <template #tooltip
            ><span class="block max-w-sm break-all whitespace-pre-line">{{
              translate('apfWorkbench.restartHelp')
            }}</span></template
          >
        </component>
      </div>
      <p
        v-if="hasUnsavedChanges"
        role="status"
        class="m-0 text-xs text-muted-foreground"
      >
        {{ translate('apfWorkbench.saveFirst') }}
      </p>
      <p
        v-if="restartMessage"
        role="status"
        class="m-0 text-xs text-muted-foreground"
      >
        {{ restartMessage }}
      </p>
      <p v-if="portChanges" class="m-0 text-xs text-muted-foreground">
        {{ translate('apfWorkbench.portChangeHelp') }}
        <a
          :href="restartAddress"
          target="_blank"
          rel="noopener noreferrer"
          class="break-all underline"
          >{{ restartAddress }}</a
        >
      </p>
    </form>

    <section v-if="configuration" class="border-t border-border-default pt-4">
      <h3 class="m-0 text-base font-medium">
        {{ translate('apfWorkbench.runtimeInfo') }}
      </h3>
      <dl
        v-if="configuration.effective"
        class="mb-0 grid gap-y-1 text-sm [&_dt]:mt-2 [&_dt]:text-xs [&_dt]:text-muted-foreground"
      >
        <dt>{{ translate('apfWorkbench.webAddress') }}</dt>
        <dd class="m-0 break-all">
          <a
            :href="configuration.effective.allowed_origins[0]"
            target="_blank"
            rel="noopener noreferrer"
            class="underline"
            >{{ configuration.effective.allowed_origins[0] }}</a
          >
        </dd>
        <dt>{{ translate('apfWorkbench.serviceAddress') }}</dt>
        <dd class="m-0 break-all">{{ serviceUrl }}</dd>
      </dl>
      <p v-else class="text-sm text-muted-foreground">
        {{ translate('apfWorkbench.noRunningValues') }}
      </p>
    </section>
  </section>
</template>

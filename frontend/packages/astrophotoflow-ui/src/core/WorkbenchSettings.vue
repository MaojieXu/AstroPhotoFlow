<script setup lang="ts">
import { computed } from 'vue'
import { useWorkbenchSettings } from './workbench/useWorkbenchSettings'

import type { Component } from 'vue'

import { ApiClientError } from './client'
import type { WorkbenchClient } from './client'

const { client, translate, controls } = defineProps<{
  client: WorkbenchClient
  controls: {
    formItem: Component
    button: Component
    input: Component
    number: Component
  }
  translate: (key: string) => string
}>()

const {
  configuration,
  form,
  defaultWorkspace,
  saved,
  hasUnsavedChanges,
  phase,
  error,
  restartMessage,
  reload,
  save,
  chooseDirectory,
  restartWorkbench
} = useWorkbenchSettings(
  () => client,
  (key) => translate(key)
)
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

const restartAddress = computed(
  () => configuration.value?.saved.allowed_origins[0]
)
const portChanges = computed(
  () =>
    restartAddress.value !== configuration.value?.effective?.allowed_origins[0]
)
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
        class="m-0 min-w-0 space-y-6 border-0 p-0"
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

        <section
          aria-labelledby="apf-workspace-settings-heading"
          class="@container space-y-4 border-t border-border-default pt-5"
        >
          <header class="flex flex-wrap items-center gap-1">
            <h3
              id="apf-workspace-settings-heading"
              class="m-0 text-base font-semibold"
            >
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
              <template #tooltip>
                <span class="block max-w-sm break-all whitespace-pre-line">{{
                  configuration.config_path
                }}</span>
              </template>
            </component>
          </header>

          <div class="grid min-w-0 gap-2">
            <div class="flex items-center gap-1">
              <label for="default_workspace" class="font-medium">
                {{ translate('apfWorkbench.defaultWorkspace') }}
              </label>
              <component
                :is="controls.button"
                type="button"
                size="icon-sm"
                variant="muted-textonly"
                icon="icon-[lucide--info]"
                :tooltip="workspaceHint"
                :aria-label="translate('apfWorkbench.workspaceHelp')"
                @click.stop
              >
                <template #tooltip>
                  <span class="block max-w-sm break-all whitespace-pre-line">{{
                    workspaceHint
                  }}</span>
                </template>
              </component>
            </div>
            <div class="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
              <component
                :is="controls.input"
                id="default_workspace"
                v-model="defaultWorkspace"
                name="default_workspace"
                :title="defaultWorkspace"
              />
              <component
                :is="controls.button"
                type="button"
                size="lg"
                icon="icon-[lucide--folder-open]"
                :aria-label="translate('apfWorkbench.chooseWorkspace')"
                @click="chooseDirectory('default_workspace')"
              >
                {{ translate('apfWorkbench.chooseDirectory') }}
              </component>
            </div>
          </div>

          <div class="grid min-w-0 gap-2">
            <div class="flex items-center gap-1">
              <label for="data_dir" class="font-medium">
                {{ translate('apfWorkbench.dataDir') }}
              </label>
              <component
                :is="controls.button"
                type="button"
                size="icon-sm"
                variant="muted-textonly"
                icon="icon-[lucide--info]"
                :tooltip="dataDirectoryHint"
                data-testid="data-directory-hint"
                :aria-label="translate('apfWorkbench.dataDirectoryDetails')"
                @click.stop
              >
                <template #tooltip>
                  <span class="block max-w-sm break-all whitespace-pre-line">{{
                    dataDirectoryHint
                  }}</span>
                </template>
              </component>
            </div>
            <div class="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
              <component
                :is="controls.input"
                id="data_dir"
                v-model="form.data_dir"
                name="data_dir"
                :title="form.data_dir"
                required
              />
              <component
                :is="controls.button"
                type="button"
                size="lg"
                icon="icon-[lucide--folder-open]"
                :aria-label="translate('apfWorkbench.chooseDataDirectory')"
                @click="chooseDirectory('data_dir')"
              >
                {{ translate('apfWorkbench.chooseDirectory') }}
              </component>
            </div>
          </div>

          <div class="grid gap-x-4 gap-y-4 @md:grid-cols-2">
            <div class="grid min-w-0 content-start gap-2">
              <label for="host" class="font-medium">
                {{ translate('apfWorkbench.host') }}
              </label>
              <component
                :is="controls.input"
                id="host"
                v-model="form.host"
                name="host"
                required
              />
            </div>
            <div class="grid min-w-0 content-start gap-2">
              <label
                id="service_port-label"
                for="service_port"
                class="font-medium"
              >
                {{ translate('apfWorkbench.servicePort') }}
              </label>
              <component
                :is="controls.number"
                id="service_port"
                v-model="form.service_port"
                name="service_port"
                aria-labelledby="service_port-label"
                :format-options="{ useGrouping: false }"
                :min="1"
                :max="65535"
                :step="1"
              />
            </div>
          </div>

          <fieldset class="m-0 min-w-0 space-y-2 border-0 p-0">
            <legend class="mb-2 p-0 font-medium">
              {{ translate('apfWorkbench.origins') }}
            </legend>
            <div
              v-for="(_, index) in form.allowed_origins"
              :key="index"
              class="flex min-w-0 items-center gap-2"
            >
              <component
                :is="controls.input"
                v-model="form.allowed_origins[index]"
                :aria-label="`${translate('apfWorkbench.origins')} ${index + 1}`"
                required
                class="min-w-0 flex-1"
              />
              <component
                :is="controls.button"
                type="button"
                variant="muted-textonly"
                @click="form.allowed_origins.splice(index, 1)"
              >
                {{ translate('apfWorkbench.remove') }}
              </component>
            </div>
            <component
              :is="controls.button"
              type="button"
              variant="textonly"
              icon="icon-[lucide--plus]"
              @click="form.allowed_origins.push('')"
            >
              {{ translate('apfWorkbench.addOrigin') }}
            </component>
          </fieldset>
        </section>
      </fieldset>

      <p v-if="saved" role="status" class="m-0 text-sm">
        {{ translate('apfWorkbench.saved') }}
      </p>
      <div class="flex flex-wrap items-center gap-2 border-t border-border-default pt-4">
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

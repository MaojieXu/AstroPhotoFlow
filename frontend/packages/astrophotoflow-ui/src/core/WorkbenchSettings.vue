<script setup lang="ts">
import {
  computed,
  onMounted,
  onBeforeUnmount,
  ref,
  shallowRef,
  toRaw
} from 'vue'

import { ApiClientError } from './client'
import type { WorkbenchClient } from './client'
import type { ConfigSave, ConfigState, ConfigValues } from './contracts'

const { client, translate } = defineProps<{
  client: WorkbenchClient
  translate: (key: string) => string
}>()

const phase = ref<'loading' | 'ready' | 'saving' | 'restarting'>('loading')
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
    class="space-y-5 p-4 text-sm font-normal text-base-foreground"
    data-testid="workbench-settings"
  >
    <header class="block min-w-0 space-y-2 font-normal">
      <p class="m-0 text-sm opacity-70">
        {{ translate('apfWorkbench.saveHelp') }}
      </p>
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
    <div
      v-if="configuration"
      class="rounded-lg border border-interface-stroke p-3"
    >
      <p class="m-0 font-medium" data-testid="configuration-state">
        {{
          translate(
            configuration.restart_required
              ? 'apfWorkbench.restartRequired'
              : 'apfWorkbench.inSync'
          )
        }}
      </p>
      <dl
        v-if="configuration.effective"
        class="mb-0 grid grid-cols-1 gap-y-1 text-sm [&_dt]:mt-2 [&_dt]:text-xs [&_dt]:text-muted-foreground"
      >
        <dt>{{ translate('apfWorkbench.webAddress') }}</dt>
        <dd class="m-0 break-all">
          <a
            :href="configuration.effective.allowed_origins[0]"
            target="_blank"
            rel="noopener noreferrer"
            class="underline decoration-interface-stroke underline-offset-4 hover:text-muted-foreground"
            >{{ configuration.effective.allowed_origins[0] }}</a
          >
        </dd>
        <dt>{{ translate('apfWorkbench.serviceAddress') }}</dt>
        <dd class="m-0 break-all">{{ serviceUrl }}</dd>
      </dl>
      <p v-else class="mb-0 text-sm opacity-70">
        {{ translate('apfWorkbench.noRunningValues') }}
      </p>
    </div>

    <form
      v-if="form && configuration"
      class="space-y-5"
      @submit.prevent="save"
      @input="saved = false"
      @click="saved = false"
    >
      <fieldset
        :disabled="phase !== 'ready'"
        class="m-0 space-y-5 border-0 p-0"
      >
        <div class="grid grid-cols-1 gap-4">
          <label class="block min-w-0 space-y-2 font-normal">
            <span class="block text-sm">{{
              translate('apfWorkbench.fileWorkers')
            }}</span>
            <input
              v-model.number="form.file_workers"
              name="file_workers"
              type="number"
              min="1"
              step="1"
              required
              class="h-9 w-full min-w-0 rounded-lg border-none bg-secondary-background px-3 text-sm font-normal text-base-foreground focus-visible:ring-1 focus-visible:ring-border-default focus-visible:outline-none"
            />
            <span
              v-if="configuration.effective"
              class="text-xs opacity-70"
              data-testid="effective-file-workers"
            >
              {{ translate('apfWorkbench.effective') }}:
              {{ configuration.effective.file_workers }}
            </span>
          </label>
          <label class="block min-w-0 space-y-2 font-normal">
            <span class="block text-sm">{{
              translate('apfWorkbench.previewWorkers')
            }}</span>
            <input
              v-model.number="form.preview_workers"
              name="preview_workers"
              type="number"
              min="1"
              step="1"
              required
              class="h-9 w-full min-w-0 rounded-lg border-none bg-secondary-background px-3 text-sm font-normal text-base-foreground focus-visible:ring-1 focus-visible:ring-border-default focus-visible:outline-none"
            />
            <span v-if="configuration.effective" class="text-xs opacity-70">
              {{ translate('apfWorkbench.effective') }}:
              {{ configuration.effective.preview_workers }}
            </span>
          </label>
        </div>

        <details class="rounded-lg border border-interface-stroke p-3">
          <summary class="cursor-pointer font-medium">
            {{ translate('apfWorkbench.advanced') }}
          </summary>
          <div class="mt-4 min-w-0 space-y-5">
            <p
              v-if="configuration"
              class="m-0 text-xs break-all text-muted-foreground"
            >
              {{ configuration.config_path }}
            </p>
            <label class="block min-w-0 space-y-2 font-normal">
              <span class="block text-sm">{{
                translate('apfWorkbench.defaultWorkspace')
              }}</span>
              <input
                v-model="defaultWorkspace"
                name="default_workspace"
                type="text"
                class="h-9 w-full min-w-0 rounded-lg border-none bg-secondary-background px-3 text-sm font-normal text-base-foreground focus-visible:ring-1 focus-visible:ring-border-default focus-visible:outline-none"
              />
              <span class="block text-xs opacity-70">{{
                translate('apfWorkbench.defaultHelp')
              }}</span>
            </label>
            <div class="grid grid-cols-1 gap-4">
              <label class="block min-w-0 space-y-2 font-normal">
                <span class="block text-sm">{{
                  translate('apfWorkbench.host')
                }}</span>
                <input
                  v-model="form.host"
                  name="host"
                  required
                  class="h-9 w-full min-w-0 rounded-lg border-none bg-secondary-background px-3 text-sm font-normal text-base-foreground focus-visible:ring-1 focus-visible:ring-border-default focus-visible:outline-none"
                />
              </label>
              <label class="block min-w-0 space-y-2 font-normal">
                <span class="block text-sm">{{
                  translate('apfWorkbench.servicePort')
                }}</span>
                <input
                  v-model.number="form.service_port"
                  name="service_port"
                  type="number"
                  min="1"
                  max="65535"
                  required
                  class="h-9 w-full min-w-0 rounded-lg border-none bg-secondary-background px-3 text-sm font-normal text-base-foreground focus-visible:ring-1 focus-visible:ring-border-default focus-visible:outline-none"
                />
              </label>
            </div>
            <label class="block min-w-0 space-y-2 font-normal">
              <span class="block text-sm">{{
                translate('apfWorkbench.dataDir')
              }}</span>
              <input
                v-model="form.data_dir"
                name="data_dir"
                required
                class="h-9 w-full min-w-0 rounded-lg border-none bg-secondary-background px-3 text-sm font-normal text-base-foreground focus-visible:ring-1 focus-visible:ring-border-default focus-visible:outline-none"
              />
            </label>
            <div class="block min-w-0 space-y-2 font-normal">
              <p class="m-0 text-sm">{{ translate('apfWorkbench.origins') }}</p>
              <div
                v-for="(_, index) in form.allowed_origins"
                :key="index"
                class="flex min-w-0 items-center gap-2"
              >
                <input
                  v-model="form.allowed_origins[index]"
                  :aria-label="translate('apfWorkbench.origins')"
                  required
                  class="h-9 min-w-0 flex-1 rounded-lg border-none bg-secondary-background px-3 text-sm font-normal text-base-foreground focus-visible:ring-1 focus-visible:ring-border-default focus-visible:outline-none"
                />
                <button
                  type="button"
                  class="inline-flex h-9 shrink-0 items-center justify-center rounded-lg border-none bg-secondary-background px-3 text-xs font-medium hover:bg-secondary-background-hover"
                  @click="form.allowed_origins.splice(index, 1)"
                >
                  {{ translate('apfWorkbench.remove') }}
                </button>
              </div>
              <button
                type="button"
                class="inline-flex min-h-8 items-center justify-center rounded-lg border-none bg-secondary-background px-3 py-2 text-xs font-medium hover:bg-secondary-background-hover"
                @click="form.allowed_origins.push('')"
              >
                {{ translate('apfWorkbench.addOrigin') }}
              </button>
            </div>
            <div class="block min-w-0 space-y-2 font-normal">
              <p class="m-0 text-sm">
                {{ translate('apfWorkbench.importRoots') }}
              </p>
              <div
                v-for="(root, index) in form.import_roots"
                :key="index"
                class="flex min-w-0 flex-wrap items-center gap-2"
              >
                <input
                  v-model="root.id"
                  :aria-label="translate('apfWorkbench.rootId')"
                  :placeholder="translate('apfWorkbench.rootId')"
                  required
                  class="h-9 w-full min-w-0 rounded-lg border-none bg-secondary-background px-3 text-sm font-normal text-base-foreground focus-visible:ring-1 focus-visible:ring-border-default focus-visible:outline-none"
                />
                <input
                  v-model="root.path"
                  :aria-label="translate('apfWorkbench.rootPath')"
                  :placeholder="translate('apfWorkbench.rootPath')"
                  required
                  class="h-9 min-w-0 flex-1 rounded-lg border-none bg-secondary-background px-3 text-sm font-normal text-base-foreground focus-visible:ring-1 focus-visible:ring-border-default focus-visible:outline-none"
                />
                <button
                  type="button"
                  class="inline-flex h-9 shrink-0 items-center justify-center rounded-lg border-none bg-secondary-background px-3 text-xs font-medium hover:bg-secondary-background-hover"
                  @click="form.import_roots.splice(index, 1)"
                >
                  {{ translate('apfWorkbench.remove') }}
                </button>
              </div>
              <button
                type="button"
                class="inline-flex min-h-8 items-center justify-center rounded-lg border-none bg-secondary-background px-3 py-2 text-xs font-medium hover:bg-secondary-background-hover"
                @click="form.import_roots.push({ id: '', path: '' })"
              >
                {{ translate('apfWorkbench.addRoot') }}
              </button>
            </div>
          </div>
        </details>
      </fieldset>
      <p v-if="saved" role="status" class="m-0 text-sm text-base-foreground">
        {{ translate('apfWorkbench.saved') }}
      </p>
      <div class="grid grid-cols-2 gap-2">
        <button
          type="submit"
          :disabled="phase !== 'ready'"
          class="inline-flex h-9 items-center justify-center rounded-lg border-none bg-primary-background px-3 text-xs font-medium text-base-foreground hover:bg-primary-background-hover disabled:opacity-50"
        >
          {{
            translate(
              phase === 'saving' ? 'apfWorkbench.saving' : 'apfWorkbench.save'
            )
          }}
        </button>
        <button
          type="button"
          :disabled="phase !== 'ready' || hasUnsavedChanges"
          data-testid="workbench-restart"
          :title="
            hasUnsavedChanges
              ? translate('apfWorkbench.saveFirst')
              : translate('apfWorkbench.restart')
          "
          class="inline-flex h-9 items-center justify-center gap-2 rounded-lg border-none bg-secondary-background px-3 text-xs font-medium text-base-foreground hover:bg-secondary-background-hover disabled:opacity-50"
          @click="restartWorkbench"
        >
          <i class="icon-[lucide--rotate-cw] size-4" aria-hidden="true" />
          {{ translate('apfWorkbench.restart') }}
        </button>
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
      <p class="m-0 text-xs text-muted-foreground">
        {{ translate('apfWorkbench.restartHelp') }}
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
    <button
      type="button"
      :disabled="phase !== 'ready'"
      class="w-full rounded-lg border-none bg-transparent px-3 py-2 text-xs font-normal text-muted-foreground hover:bg-secondary-background-hover disabled:opacity-50"
      @click="reload"
    >
      {{ translate('apfWorkbench.reload') }}
    </button>
  </section>
</template>

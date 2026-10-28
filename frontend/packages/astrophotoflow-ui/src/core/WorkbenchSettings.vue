<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, toRaw } from 'vue'

import { ApiClientError } from './client'
import type { WorkbenchClient } from './client'
import type { ConfigSave, ConfigState, ConfigValues } from './contracts'

const { client, translate } = defineProps<{
  client: WorkbenchClient
  translate: (key: string) => string
}>()

const phase = ref<'loading' | 'ready' | 'saving'>('loading')
const configuration = ref<ConfigState | null>(null)
const form = ref<ConfigValues | null>(null)
const defaultWorkspace = ref('')
const error = shallowRef<unknown>(null)
const saved = ref(false)
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

onMounted(reload)
</script>

<template>
  <section class="space-y-5" data-testid="workbench-settings">
    <header class="space-y-2">
      <h2 class="m-0 text-xl font-semibold">
        {{ translate('apfWorkbench.title') }}
      </h2>
      <p class="m-0 text-sm opacity-70">
        {{ translate('apfWorkbench.saveHelp') }}
      </p>
      <p v-if="configuration" class="m-0 break-all text-xs opacity-70">
        {{ configuration.config_path }}
      </p>
    </header>

    <div
      v-if="error"
      role="alert"
      class="rounded-lg border border-red-500/50 bg-red-500/10 p-3"
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
      <p v-if="requestError?.requestId" class="mb-0 break-all text-xs">
        {{ translate('apfWorkbench.requestId') }}: {{ requestError.requestId }}
      </p>
    </div>

    <p v-if="phase === 'loading'" role="status">
      {{ translate('apfWorkbench.loading') }}
    </p>
    <div v-if="configuration" class="rounded-lg border border-current/20 p-3">
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
        class="mb-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm"
      >
        <dt>{{ translate('apfWorkbench.webAddress') }}</dt>
        <dd class="m-0 break-all">
          {{ configuration.effective.allowed_origins[0] }}
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
        <div class="grid grid-cols-2 gap-4">
          <label class="space-y-2">
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
              class="w-full rounded border border-current/20 bg-transparent px-3 py-2"
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
          <label class="space-y-2">
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
              class="w-full rounded border border-current/20 bg-transparent px-3 py-2"
            />
            <span v-if="configuration.effective" class="text-xs opacity-70">
              {{ translate('apfWorkbench.effective') }}:
              {{ configuration.effective.preview_workers }}
            </span>
          </label>
        </div>

        <details class="rounded-lg border border-current/20 p-3">
          <summary class="cursor-pointer font-medium">
            {{ translate('apfWorkbench.advanced') }}
          </summary>
          <div class="mt-4 space-y-4">
            <label class="block space-y-2">
              <span class="block text-sm">{{
                translate('apfWorkbench.defaultWorkspace')
              }}</span>
              <input
                v-model="defaultWorkspace"
                name="default_workspace"
                type="text"
                class="w-full rounded border border-current/20 bg-transparent px-3 py-2"
              />
              <span class="block text-xs opacity-70">{{
                translate('apfWorkbench.defaultHelp')
              }}</span>
            </label>
            <div class="grid grid-cols-2 gap-4">
              <label class="space-y-2">
                <span class="block text-sm">{{
                  translate('apfWorkbench.host')
                }}</span>
                <input
                  v-model="form.host"
                  name="host"
                  required
                  class="w-full rounded border border-current/20 bg-transparent px-3 py-2"
                />
              </label>
              <label class="space-y-2">
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
                  class="w-full rounded border border-current/20 bg-transparent px-3 py-2"
                />
              </label>
            </div>
            <label class="block space-y-2">
              <span class="block text-sm">{{
                translate('apfWorkbench.dataDir')
              }}</span>
              <input
                v-model="form.data_dir"
                name="data_dir"
                required
                class="w-full rounded border border-current/20 bg-transparent px-3 py-2"
              />
            </label>
            <div class="space-y-2">
              <p class="m-0 text-sm">{{ translate('apfWorkbench.origins') }}</p>
              <div
                v-for="(_, index) in form.allowed_origins"
                :key="index"
                class="flex gap-2"
              >
                <input
                  v-model="form.allowed_origins[index]"
                  :aria-label="translate('apfWorkbench.origins')"
                  required
                  class="min-w-0 flex-1 rounded border border-current/20 bg-transparent px-3 py-2"
                />
                <button
                  type="button"
                  class="rounded border border-current/20 px-3 hover:bg-white/10"
                  @click="form.allowed_origins.splice(index, 1)"
                >
                  {{ translate('apfWorkbench.remove') }}
                </button>
              </div>
              <button
                type="button"
                class="rounded border border-current/20 px-3 py-2 hover:bg-white/10"
                @click="form.allowed_origins.push('')"
              >
                {{ translate('apfWorkbench.addOrigin') }}
              </button>
            </div>
            <div class="space-y-2">
              <p class="m-0 text-sm">
                {{ translate('apfWorkbench.importRoots') }}
              </p>
              <div
                v-for="(root, index) in form.import_roots"
                :key="index"
                class="flex flex-wrap gap-2"
              >
                <input
                  v-model="root.id"
                  :aria-label="translate('apfWorkbench.rootId')"
                  :placeholder="translate('apfWorkbench.rootId')"
                  required
                  class="w-28 rounded border border-current/20 bg-transparent px-3 py-2"
                />
                <input
                  v-model="root.path"
                  :aria-label="translate('apfWorkbench.rootPath')"
                  :placeholder="translate('apfWorkbench.rootPath')"
                  required
                  class="min-w-0 flex-1 rounded border border-current/20 bg-transparent px-3 py-2"
                />
                <button
                  type="button"
                  class="rounded border border-current/20 px-3 hover:bg-white/10"
                  @click="form.import_roots.splice(index, 1)"
                >
                  {{ translate('apfWorkbench.remove') }}
                </button>
              </div>
              <button
                type="button"
                class="rounded border border-current/20 px-3 py-2 hover:bg-white/10"
                @click="form.import_roots.push({ id: '', path: '' })"
              >
                {{ translate('apfWorkbench.addRoot') }}
              </button>
            </div>
          </div>
        </details>
      </fieldset>
      <p v-if="saved" role="status" class="m-0 text-sm text-green-500">
        {{ translate('apfWorkbench.saved') }}
      </p>
      <button
        type="submit"
        :disabled="phase !== 'ready'"
        class="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-500 disabled:opacity-50"
      >
        {{
          translate(
            phase === 'saving' ? 'apfWorkbench.saving' : 'apfWorkbench.save'
          )
        }}
      </button>
    </form>
    <button
      type="button"
      :disabled="phase !== 'ready'"
      class="rounded-lg border border-current/20 px-3 py-2 hover:bg-white/10 disabled:opacity-50"
      @click="reload"
    >
      {{ translate('apfWorkbench.reload') }}
    </button>
  </section>
</template>

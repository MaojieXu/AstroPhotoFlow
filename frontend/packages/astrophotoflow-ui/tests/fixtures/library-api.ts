import type { ServiceHealth } from '../../src/generated/api/types.gen'

import { createDisplayPreviewClient } from '../../src/modules/data/api/display'
import { zDisplayPreviewState } from '../../src/generated/api/zod.gen'
import { createDatasetClient } from '../../src/modules/data/api/datasets'
import { createAssetClient } from '../../src/modules/data/api/assets'
import { zAssetContentObservation } from '../../src/generated/api/zod.gen'
import { zLocalSelectionOut } from '../../src/generated/api/zod.gen'
import { createImportClient } from '../../src/modules/data/api/imports'
import {
  zImportAccepted,
  zImportTaskStateOut
} from '../../src/generated/api/zod.gen'
import { createTrashClient } from '../../src/modules/data/api/trash'
import {
  zManagementTrashPreviewOut,
  zManagementTrashDeleteOut,
  zLibraryTrashPreviewOut,
  zLibraryTrashDeleteOut,
  zLibraryTrashRestoreOut
} from '../../src/generated/api/zod.gen'
import {
  zProjectAssetReferenceOut,
  zProjectDatasetReferenceOut,
  zProjectReferenceDeleteResult
} from '../../src/generated/api/zod.gen'
import {
  zDatasetMemberParametersUpdateOut,
  zLibraryEntriesRemoveOut
} from '../../src/generated/api/zod.gen'
import {
  zAssetOut,
  zDatasetOut,
  zProjectOut,
  zEquipmentSetupOut,
  zManagementArchiveResult
} from '../../src/generated/api/zod.gen'
import { createMutationClient } from '../../src/modules/data/api/mutations'
import { createCatalogClient } from '../../src/modules/data/api/catalog'
import { createLibraryClient } from '../../src/modules/data/library/client'
import { libraryAsset } from './library-summary'
import { ApiClientError } from '../../src/core/api/errors'
import {
  zLibraryFilterOptions,
  zLibraryItemPage,
  zDatasetMemberPage,
  zProjectPage,
  zProjectAssetReferencePage,
  zProjectDatasetReferencePage,
  zDatasetPage,
  zEquipmentPage
} from '../../src/generated/api/zod.gen'

/** Existing component fixtures act as the server; exercise the real SDK adapter. */
export const workspaceHealth: ServiceHealth = {status:'ok',api_version:'v1',database:'ready',schema_revision:'0001',workspace:'/test-workspace'}

export function createLibraryApiFixture(
  get: (
    path: string,
    schema?: unknown,
    signal?: AbortSignal
  ) => unknown | Promise<unknown>
) {
  let revision = 0
  return fixtureFetch(async (path, schema, signal) => {
    if (path.endsWith('/library/change-state')) return {revision_token:String(++revision),thumbnail_token:'fixture'}
    if (!path.includes('/member-summaries?')) return get(path, schema, signal)
    const body = zDatasetMemberPage.parse(await get(path.replace('/member-summaries?', '/members?'), schema, signal))
    const datasetId = /\/datasets\/([^/]+)\//.exec(path)![1]
    return { ...body, items: body.items.map(member => ({
      ...libraryAsset(member.asset),
      dataset_id: datasetId, member_position: member.position,
      thumbnail_status: null
    })) }
  }, createLibraryClient)
}

export function createCatalogApiFixture(
  get: (
    path: string,
    schema?: unknown,
    signal?: AbortSignal
  ) => unknown | Promise<unknown>
) {
  // Component scenarios share one explicit isolated workspace. Health behavior
  // itself is exercised by transport/API tests rather than unrelated list doubles.
  return fixtureFetch((path, schema, signal) =>
    path.endsWith('/health') ? workspaceHealth : get(path, schema, signal), createCatalogClient)
}

function fixtureFetch<T>(
  get: (
    path: string,
    schema?: unknown,
    signal?: AbortSignal
  ) => unknown | Promise<unknown>,
  create: (fetch: (path: string, init?: RequestInit) => Promise<Response>) => T
): T {
  return create(async (path, init) => {
    try {
      const body = await get(path, undefined, init?.signal ?? undefined)
      const schema = path.includes('/filter-options')
        ? zLibraryFilterOptions
        : path.includes('/library/items')
          ? zLibraryItemPage
          : path.includes('/members?')
            ? zDatasetMemberPage
            : /\/projects\/[^/]+\/assets\?/.test(path)
              ? zProjectAssetReferencePage
              : /\/projects\/[^/]+\/datasets\?/.test(path)
                ? zProjectDatasetReferencePage
                : path.includes('/projects?')
                  ? zProjectPage
                  : path.includes('/datasets?')
                    ? zDatasetPage
                    : path.includes('/equipment?')
                      ? zEquipmentPage
                      : undefined
      const checked = schema?.safeParse(body)
      if (checked && !checked.success)
        console.error(
          'Invalid library fixture',
          path,
          checked.error.issues
            .slice(0, 8)
            .map((issue) => `${issue.path.join('.')}:${issue.code}`)
        )
      return Response.json(body)
    } catch (error) {
      if (error instanceof ApiClientError && error.kind === 'service') {
        return Response.json(
          {
            error: {
              code: error.code ?? 'SERVICE_ERROR',
              message: error.message,
              fields: error.fields ?? []
            },
            request_id:
              error.requestId ?? '00000000-0000-4000-8000-000000000001'
          },
          { status: error.status ?? 500 }
        )
      }
      throw error
    }
  })
}

export function createMutationApiFixture(
  send: (
    path: string,
    schema: unknown,
    method: string,
    body: unknown,
    options?: Pick<RequestInit, 'signal'>
  ) => unknown | Promise<unknown>
) {
  return mutationFixture(send, createMutationClient)
}

function mutationFixture<T>(
  send: (
    path: string,
    schema: unknown,
    method: string,
    body: unknown,
    options?: Pick<RequestInit, 'signal'>
  ) => unknown | Promise<unknown>,
  create: (fetch: (path: string, init?: RequestInit) => Promise<Response>) => T
): T {
  return create(async (path, init) => {
    try {
      const body =
        typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
      const schema = path.endsWith('/display/auto-stretch')?zDisplayPreviewState:path.endsWith('/datasets')?zDatasetOut:path.endsWith('/content-observation') ? zAssetContentObservation : path.endsWith('/imports/select-local')
        ? zLocalSelectionOut
        : path.endsWith('/imports') || path.endsWith('/retry')
          ? zImportAccepted
          : path.endsWith('/resume')
            ? zImportTaskStateOut
            : path.includes('/equipment-management/')
              ? path.endsWith('/delete-preview')
                ? zManagementTrashPreviewOut
                : zManagementTrashDeleteOut
              : path.includes('/library/trash/')
                ? path.endsWith('/restore')
                  ? zLibraryTrashRestoreOut
                  : path.endsWith('/delete-preview')
                    ? zLibraryTrashPreviewOut
                    : zLibraryTrashDeleteOut
                : path.includes('/asset-references') ||
                    path.includes('/dataset-references')
                  ? init?.method === 'DELETE'
                    ? zProjectReferenceDeleteResult
                    : path.includes('/asset-references')
                      ? zProjectAssetReferenceOut
                      : zProjectDatasetReferenceOut
                  : path.endsWith('/member-parameters')
                    ? zDatasetMemberParametersUpdateOut
                    : path.endsWith('/library/items')
                      ? zLibraryEntriesRemoveOut
                      : path.includes('/settings/trash/archive')
                        ? zManagementArchiveResult
                        : path.includes('/library/assets/')
                          ? zAssetOut
                          : path.includes('/equipment-setups')
                              ? zEquipmentSetupOut
                              : path.includes('/equipment')
                                ? zEquipmentPage.shape.items.element
                                : path.includes('/datasets/')
                                  ? zDatasetOut
                                  : zProjectOut
      const response = path.endsWith('/imports/select-local')
        ? await send(path, schema, init?.method ?? 'POST', body, {
            signal: init?.signal
          })
        : await send(path, schema, init?.method ?? 'POST', body)
      const checked = schema.safeParse(response)
      if (!checked.success)
        console.error(
          'Invalid mutation fixture',
          path,
          checked.error.issues
            .slice(0, 8)
            .map((issue) => issue.path.join('.') + ':' + issue.code)
        )
      return Response.json(response)
    } catch (error) {
      if (error instanceof TypeError) throw error
      const status =
        error instanceof ApiClientError ? (error.status ?? 500) : 500
      return Response.json(
        {
          error: {
            code:
              error instanceof ApiClientError
                ? (error.code ?? 'SERVICE_ERROR')
                : 'SERVICE_ERROR',
            message: error instanceof Error ? error.message : String(error),
            fields: error instanceof ApiClientError ? (error.fields ?? []) : []
          },
          request_id: '00000000-0000-4000-8000-000000000001'
        },
        { status }
      )
    }
  })
}

export function createTrashApiFixture(
  get: (
    path: string,
    schema?: unknown,
    signal?: AbortSignal
  ) => unknown | Promise<unknown>,
  send: (
    path: string,
    schema: unknown,
    method: string,
    body: unknown,
    options?: Pick<RequestInit, 'signal'>
  ) => unknown | Promise<unknown>
) {
  const read = fixtureFetch(get, (fetch) => fetch)
  const write = mutationFixture(send, (fetch) => fetch)
  return createTrashClient((path, init) =>
    init?.method === 'GET' ? read(path, init) : write(path, init)
  )
}

export function createImportApiFixture(
  get: (
    path: string,
    schema?: unknown,
    signal?: AbortSignal
  ) => unknown | Promise<unknown>,
  send: (
    path: string,
    schema: unknown,
    method: string,
    body: unknown,
    options?: Pick<RequestInit, 'signal'>
  ) => unknown | Promise<unknown>
) {
  const read = fixtureFetch(get, (fetch) => fetch),
    write = mutationFixture(send, (fetch) => fetch)
  return createImportClient((path, init) =>
    init?.method === 'GET' ? read(path, init) : write(path, init)
  )
}

export function createAssetApiFixture(
 get: Parameters<typeof createCatalogApiFixture>[0],
 send: Parameters<typeof createMutationApiFixture>[0]
){
 const read=fixtureFetch(get,fetch=>fetch)
 const write=mutationFixture(send,fetch=>fetch)
 return createAssetClient((path,init)=>init?.method==='GET'?read(path,init):write(path,init))
}

export function createDatasetApiFixture(
 get: Parameters<typeof createCatalogApiFixture>[0],
 send: Parameters<typeof createMutationApiFixture>[0]
){
 const read=fixtureFetch(get,fetch=>fetch)
 const write=mutationFixture(send,fetch=>fetch)
 return createDatasetClient((path,init)=>init?.method==='GET'?read(path,init):write(path,init))
}

export function createDisplayPreviewApiFixture(
 get: Parameters<typeof createCatalogApiFixture>[0],
 send: Parameters<typeof createMutationApiFixture>[0],
 getBlob:(path:string)=>Promise<Blob>
){
 const read=fixtureFetch(get,fetch=>fetch)
 const write=mutationFixture(send,fetch=>fetch)
 return createDisplayPreviewClient(async(path,init)=>{
  if(path.endsWith('/display')){const blob=await getBlob(path);return new Response(blob,{headers:{'Content-Type':blob.type}})}
  return init?.method==='GET'?read(path,init):write(path,init)
 })
}

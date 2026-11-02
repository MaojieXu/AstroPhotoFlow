import { createDisplayPreviewClient } from './display'
import { createDatasetClient } from './datasets'
import { createAssetClient } from './assets'
import { createImportClient } from './imports'
import { createTrashClient } from './trash'
import { createMutationClient } from './mutations'
import { createCatalogClient } from './catalog'
import { createLibraryClient } from '../library/client'
import { createPreviewImageClient } from '../../../core/api/images'

export const assetApi = createPreviewImageClient((path, init) => fetch(path, init))

export const libraryApi = createLibraryClient((path, init) => fetch(path, init))

export const catalogApi = createCatalogClient((path, init) => fetch(path, init))

export const mutationApi = createMutationClient((path,init)=>fetch(path,init))

export const trashApi = createTrashClient((path,init)=>fetch(path,init))

export const importApi = createImportClient((path,init)=>fetch(path,init))

export const assetDetailsApi = createAssetClient((path,init)=>fetch(path,init))

export const datasetApi = createDatasetClient((path,init)=>fetch(path,init))

export const displayPreviewApi=createDisplayPreviewClient((path,init)=>fetch(path,init))

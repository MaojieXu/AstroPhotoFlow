import { createApiClient } from './client'

export const assetApi = createApiClient((path, init) => fetch(path, init))

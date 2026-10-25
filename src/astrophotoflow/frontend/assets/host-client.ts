import { api } from '../../../scripts/api.js'
import { createApiClient } from './client'

export const assetApi = createApiClient(api.fetchApi.bind(api))

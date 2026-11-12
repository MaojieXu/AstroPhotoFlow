import { createPlatformClient } from '../../core/api/client'
import type { FetchApi } from '../../core/api/client'
import {
  nodesApiV1NodesGet,
  nodeApiV1NodesDefinitionIdGet
} from '../../generated/api/sdk.gen'
import type { NodeCapability } from '../../generated/api/types.gen'

export {
  zParameterDefinition as nodeParameterSchema,
  zSavedDefinition as savedNodeSchema,
  zNodeCapability as nodeCapabilitySchema
} from '../../generated/api/zod.gen'
export type {
  NodeCapability,
  SavedDefinition as SavedNode,
  ParameterDefinition as NodeParameter
} from '../../generated/api/types.gen'

export function createNodeClient(fetchApi: FetchApi) {
  const options = {
    client: createPlatformClient({ fetchApi }),
    throwOnError: true
  } as const
  return {
    async list(): Promise<NodeCapability[]> {
      return (await nodesApiV1NodesGet<true>(options)).data
    },
    async get(id: string): Promise<NodeCapability> {
      return (
        await nodeApiV1NodesDefinitionIdGet<true>({
          ...options,
          path: { definition_id: id }
        })
      ).data
    }
  }
}

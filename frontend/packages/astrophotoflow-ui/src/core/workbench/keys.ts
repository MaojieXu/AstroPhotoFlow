import type { WorkbenchClient } from '../client'
import { toRaw } from 'vue'

// The control source is unknown until configuration is read. Never hash a client
// object (its functions disappear during serialization) or share another source.
const clients = new WeakMap<WorkbenchClient, number>()
let nextClientId = 0
export function workbenchKey(client: WorkbenchClient) {
  client = toRaw(client)
  let id = clients.get(client)
  if (id === undefined) {
    id = ++nextClientId
    clients.set(client, id)
  }
  return ['workbench-control', id] as const
}
export const configurationKey = (client: WorkbenchClient) =>
  [...workbenchKey(client), 'configuration'] as const

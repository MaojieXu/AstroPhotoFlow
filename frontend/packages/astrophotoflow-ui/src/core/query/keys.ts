export function workspaceQueryKey(workspaceId: string) {
  return ['workspace', workspaceId] as const
}

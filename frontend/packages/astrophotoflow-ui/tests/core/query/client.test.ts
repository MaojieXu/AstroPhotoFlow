import { onlineManager } from '@tanstack/vue-query'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createPlatformQueryClient } from '@ui/core/query/client'
import { workspaceQueryKey } from '@ui/core/query/keys'

afterEach(() => onlineManager.setOnline(true))

describe('local platform query policy', () => {
  it('reads and writes while the browser reports no internet connection', async () => {
    onlineManager.setOnline(false)
    const client = createPlatformQueryClient()
    try {
      const read = vi.fn().mockResolvedValue('local result')
      const write = vi.fn().mockResolvedValue('saved locally')
      await expect(client.fetchQuery({ queryKey: workspaceQueryKey('/one'), queryFn: read })).resolves.toBe('local result')
      await expect(client.getMutationCache().build(client, { mutationFn: write }).execute(undefined)).resolves.toBe('saved locally')
      expect(read).toHaveBeenCalledTimes(1)
      expect(write).toHaveBeenCalledTimes(1)
    } finally {
      client.clear()
    }
  })

  it('exposes a failed local request without replaying either reads or writes', async () => {
    const client = createPlatformQueryClient()
    try {
      const failure = new Error('The request outcome is unknown')
      const read = vi.fn().mockRejectedValue(failure)
      const write = vi.fn().mockRejectedValue(failure)
      await expect(client.fetchQuery({ queryKey: workspaceQueryKey('/one'), queryFn: read })).rejects.toBe(failure)
      await expect(client.getMutationCache().build(client, { mutationFn: write }).execute(undefined)).rejects.toBe(failure)
      expect(read).toHaveBeenCalledTimes(1)
      expect(write).toHaveBeenCalledTimes(1)
    } finally {
      client.clear()
    }
  })
})

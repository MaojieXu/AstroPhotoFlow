/** Combine explicit all-mode reads; never publish an incomplete set of pages. */
export async function readPages<P extends { items: unknown[]; total: number; limit: number; offset: number }>(
  read: (offset?: number) => Promise<P>,
  all: boolean,
  signal: AbortSignal
): Promise<P> {
  signal.throwIfAborted()
  const first = await read()
  signal.throwIfAborted()
  if (!all) return first
  const items = [...first.items]
  for (let offset = first.offset + first.limit; offset < first.total; offset += first.limit) {
    signal.throwIfAborted()
    const page = await read(offset)
    signal.throwIfAborted()
    items.push(...page.items)
  }
  return { ...first, items }
}

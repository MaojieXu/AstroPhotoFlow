import assert from 'node:assert/strict'
import { createClient } from '../../.artifacts/reports/modernization/g0/generated/client'
import { probeBinary, probeQuery, probeSample } from '../../.artifacts/reports/modernization/g0/generated/sdk.gen'
import { zErrorReply, zSample } from '../../.artifacts/reports/modernization/g0/generated/zod.gen'
import { probeQueryOptions } from '../../.artifacts/reports/modernization/g0/generated/@tanstack/vue-query.gen'

const sample = {
  equipment: { kind: 'camera' as const, gain: 0 },
  observed_at: '2026-10-31T00:00:00Z',
  required_nullable: null,
}
assert.equal(zSample.parse(sample).equipment.kind, 'camera')
assert.equal(zSample.safeParse({ ...sample, required_nullable: undefined }).success, false)
assert.equal(zSample.safeParse({ ...sample, optional_nullable: null }).success, true)
assert.equal(zSample.safeParse({ ...sample, observed_at: 'invalid' }).success, false)
assert.equal(zSample.safeParse({ ...sample, observed_at: '2026-10-31T08:00:00+08:00' }).success, true)
assert.equal(zSample.safeParse({ ...sample, equipment: { kind: 'filter', bandwidth: null } }).success, true)
assert.equal(zSample.safeParse({ ...sample, equipment: { kind: 'filter', gain: 0 } }).success, false)
assert.equal(zErrorReply.safeParse({ error: { code: 'INVALID', message: 'invalid' }, request_id: 'probe' }).success, true)

const client = createClient({
  baseUrl: 'http://contract.invalid',
  fetch: async (request) => {
    const url = new URL(request instanceof Request ? request.url : String(request))
    if (url.pathname === '/binary') {
      return new Response(new Uint8Array([1, 2, 3]), { headers: { 'Content-Type': 'image/png' } })
    }
    if (request instanceof Request && request.method === 'POST') {
      return Response.json(await request.json())
    }
    assert.deepEqual(url.searchParams.getAll('tags'), ['相机', 'gain'])
    return Response.json(['相机', 'gain'])
  },
})
assert.equal((await probeSample({ client, body: sample, throwOnError: true })).data?.equipment.kind, 'camera')
assert.deepEqual((await probeQuery({ client, query: { tags: ['相机', 'gain'] }, throwOnError: true })).data, ['相机', 'gain'])
const binary = await probeBinary({ client, throwOnError: true })
assert(binary.data instanceof Blob)
assert.equal(binary.data.size, 3)
const invalid = createClient({ baseUrl: 'http://contract.invalid', fetch: async () => Response.json({ invalid: true }) })
await assert.rejects(() => probeSample({ client: invalid, body: sample, throwOnError: true }))
const failure = { error: { code: 'INVALID', message: 'invalid' }, request_id: 'probe' }
const failed = createClient({ baseUrl: 'http://contract.invalid', fetch: async () => Response.json(failure, { status: 422 }) })
assert.deepEqual((await probeSample({ client: failed, body: sample })).error, failure)
const options = probeQueryOptions({ client, query: { tags: ['相机', 'gain'] } })
assert(options.queryKey)
assert.equal(typeof options.queryFn, 'function')
console.log('G0 generated SDK: nullability, union, date, query arrays, binary, errors and response validation passed')

import { afterEach, describe, expect, it, vi } from 'vitest'

import { ComfyApi } from '@/scripts/api'

class FakeWebSocket extends EventTarget {
  static readonly OPEN = 1
  static instances: FakeWebSocket[] = []
  readyState = FakeWebSocket.OPEN
  send = vi.fn()
  constructor() {
    super()
    FakeWebSocket.instances.push(this)
  }
  close() {
    this.readyState = 3
    this.dispatchEvent(new Event('close'))
  }
  message(data: unknown) {
    this.dispatchEvent(new MessageEvent('message', { data: JSON.stringify(data) }))
  }
  open() { this.dispatchEvent(new Event('open')) }
}

describe('ComfyApi native page events', () => {
  afterEach(() => {
    FakeWebSocket.instances = []
    vi.unstubAllGlobals()
  })

  it('sends confirmation over the existing socket and resolves its matching page result', async () => {
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    const api = new ComfyApi()
    await api.init()
    const socket = FakeWebSocket.instances[0]
    socket.open()
    socket.message({ type: 'feature_flags', data: { apf_page: true } })

    const openMessage = JSON.parse(socket.send.mock.calls[1][0])
    expect(openMessage.type).toBe('apf.page')
    expect(openMessage.data).toMatchObject({ action: 'open', payload: null })
    socket.message({
      type: 'apf.page_result',
      data: {
        event_id: openMessage.data.event_id,
        page_id: '22222222-2222-4222-8222-222222222222',
        page_token: 'current-page-token',
        result: null,
        error: null
      }
    })

    const result = api.sendNativePage('confirm_software', { operation_id: '11111111-1111-4111-8111-111111111111' })
    const confirmation = JSON.parse(socket.send.mock.calls[2][0])
    expect(confirmation.data).toMatchObject({
      action: 'confirm_software',
      payload: { operation_id: '11111111-1111-4111-8111-111111111111' }
    })
    expect(confirmation.data).not.toHaveProperty('page_id')
    expect(confirmation.data).not.toHaveProperty('page_token')

    socket.message({
      type: 'apf.page_result',
      data: {
        event_id: confirmation.data.event_id,
        page_id: '22222222-2222-4222-8222-222222222222',
        page_token: 'current-page-token',
        result: null,
        error: null
      }
    })
    await expect(result).resolves.toMatchObject({ ok: true, reply: { page_token: 'current-page-token' } })
  })

  it('returns connection_closed for a pending event without replaying it', async () => {
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    const api = new ComfyApi()
    api.serverFeatureFlags.value = { apf_page: true }
    await api.init()
    const socket = FakeWebSocket.instances[0]
    socket.open()
    const pending = api.sendNativePage('confirm_software', { operation_id: '11111111-1111-4111-8111-111111111111' })
    socket.close()
    api.socket = null
    await expect(pending).resolves.toEqual({ ok: false, reason: 'connection_closed' })
    expect(socket.send).toHaveBeenCalledTimes(2)
  })
  it('rejects a malformed correlated reply without replaying the confirmation',async()=>{
    FakeWebSocket.instances=[]
    vi.stubGlobal('WebSocket',FakeWebSocket)
    const api=new ComfyApi()
    api.serverFeatureFlags.value={apf_page:true}
    await api.init()
    const socket=FakeWebSocket.instances[0]
    socket.open()
    const pending=api.sendNativePage('confirm_software',{operation_id:'11111111-1111-4111-8111-111111111111'})
    const confirmation=socket.send.mock.calls.map(([text])=>JSON.parse(text)).find(message=>message.data?.action==='confirm_software')
    const sends=socket.send.mock.calls.length
    socket.message({type:'apf.page_result',data:{event_id:confirmation.data.event_id,
      page_id:'22222222-2222-4222-8222-222222222222',page_token:'current',result:{invented:true},error:null}})
    await expect(pending).resolves.toEqual({ok:false,reason:'invalid_response'})
    expect(socket.send).toHaveBeenCalledTimes(sends)
    api.socket=null
  })

})

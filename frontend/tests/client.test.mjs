import test from 'node:test'
import assert from 'node:assert/strict'
import { streamChat, listTemplates } from '../src/api/client.ts'

test('事件流跨 UTF-8 字节分片、心跳及 CRLF 仍按顺序解析', async () => {
  const original = globalThis.fetch
  const bytes = new TextEncoder().encode(': heartbeat\r\n\r\nevent: thinking\r\ndata: {"text":"正在思考"}\r\n\r\nevent: result\r\ndata: {"task_id":"abc"}\r\n\r\n')
  globalThis.fetch = async () => new Response(new ReadableStream({ start(controller) { for (const byte of bytes) controller.enqueue(Uint8Array.of(byte)); controller.close() } }), { headers: { 'content-type': 'text/event-stream' } })
  try {
    const events = []
    await streamChat({ message: '测试', file: null, templateKey: null, previousTaskId: null }, new AbortController().signal, (event) => events.push(event))
    assert.deepEqual(events.map((event) => event.event), ['thinking', 'result'])
    assert.equal(events[0].data.text, '正在思考')
  } finally { globalThis.fetch = original }
})

test('模板空页仍继续读取后续页', async () => {
  const original = globalThis.fetch
  let count = 0
  globalThis.fetch = async (url) => {
    count++
    if (count === 1) return Response.json({ items: [], is_truncated: true, next_continuation_token: 'next' })
    assert.match(String(url), /continuation_token=next/)
    return Response.json({ items: [{ object_key: 'a.pptx' }], is_truncated: false, next_continuation_token: null })
  }
  try { assert.equal((await listTemplates(new AbortController().signal))[0].object_key, 'a.pptx') }
  finally { globalThis.fetch = original }
})

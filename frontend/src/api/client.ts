import type { StreamEvent, Template } from './contracts'

/** 使用 Vite 代理访问同源 API，生产部署需将同一路径代理到后端。 */
const base = '/ppt-agent/v1'

async function failure(response: Response): Promise<Error> {
  try {
    const body = await response.json()
    return new Error(typeof body.detail?.message === 'string' ? body.detail.message : `请求失败（${response.status}）`)
  } catch { return new Error(`请求失败（${response.status}）`) }
}

export async function listTemplates(signal: AbortSignal): Promise<Template[]> {
  const items: Template[] = []
  let cursor: string | null = null
  const seen = new Set<string>()
  do {
    const query = new URLSearchParams({ max_keys: '100' })
    if (cursor) query.set('continuation_token', cursor)
    const response = await fetch(`${base}/templates?${query}`, { signal })
    if (!response.ok) throw await failure(response)
    const page = await response.json()
    if (!Array.isArray(page.items) || typeof page.is_truncated !== 'boolean') throw new Error('模板列表响应格式无效。')
    items.push(...page.items)
    cursor = page.is_truncated ? page.next_continuation_token : null
    if (page.is_truncated && (typeof cursor !== 'string' || !cursor || seen.has(cursor))) throw new Error('模板列表分页游标无效。')
    if (cursor) seen.add(cursor)
  } while (cursor)
  return items
}

/** 增量解码 SSE 帧，支持跨网络分片的 UTF-8 字符、CRLF 和心跳注释。 */
export async function streamChat(input: { message: string; file: File | null; templateKey: string | null; previousTaskId: string | null }, signal: AbortSignal, onEvent: (event: StreamEvent) => void) {
  const form = new FormData()
  form.set('message', input.message)
  if (input.file) form.set('file', input.file)
  if (input.templateKey) form.set('template_key', input.templateKey)
  if (input.previousTaskId) form.set('previous_task_id', input.previousTaskId)
  const response = await fetch(`${base}/chat/stream`, { method: 'POST', body: form, signal, headers: { Accept: 'text/event-stream' } })
  if (!response.ok) throw await failure(response)
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) throw new Error('服务未返回有效的事件流。')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let terminal = false
  function frame(raw: string) {
    let event = 'message'
    const data: string[] = []
    for (const line of raw.split(/\r\n|\r|\n/)) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''))
    }
    if (!data.length) return
    const parsed = JSON.parse(data.join('\n')) as Record<string, unknown>
    onEvent({ event, data: parsed })
    if (event === 'result' || event === 'error') terminal = true
  }
  try {
    while (true) {
      const chunk = await reader.read()
      buffer += decoder.decode(chunk.value, { stream: !chunk.done })
      let boundary: RegExpExecArray | null
      while ((boundary = /\r\n\r\n|\n\n|\r\r/.exec(buffer))) {
        frame(buffer.slice(0, boundary.index))
        buffer = buffer.slice(boundary.index + boundary[0].length)
      }
      if (chunk.done) break
    }
    if (buffer.trim()) frame(buffer)
    if (!terminal) throw new Error('连接已结束，但未收到最终结果，请重试。')
  } finally { reader.releaseLock() }
}

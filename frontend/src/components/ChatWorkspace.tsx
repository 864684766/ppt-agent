import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowUp, FileText, Paperclip, Sparkles, Square, X } from 'lucide-react'
import { streamChat } from '../api/client'
import type { ChatResult, Outline, Question, Template } from '../api/contracts'
import { Button } from './ui/button'
import { OutlinePanel } from './OutlinePanel'

type Turn = { id: number; message: string; fileName: string | null; progress: string[]; thinking: string; result: ChatResult | null; error: string; running: boolean }
function QuestionCard({ question }: { question: Question }) {
  return <div className="question-card"><div className="question-title"><strong>需要你的想法</strong></div><p>{question.question}</p>{question.reason && <p>{question.reason}</p>}<p className="question-hint">可以在下方补充文字或附件，作为新一轮资料提交。原问题的选项恢复接口尚未接入。</p></div>
}

export function ChatWorkspace({ selected }: { selected: Template | null }) {
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [view, setView] = useState<'chat' | 'outline'>('chat')
  const [outline, setOutline] = useState<Outline | null>(null)
  const [draft, setDraft] = useState(false)
  const [notice, setNotice] = useState('')
  const [previousTaskId, setPreviousTaskId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const controller = useRef<AbortController | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const scroll = useRef<HTMLDivElement>(null)
  const nextId = useRef(0)
  useEffect(() => () => controller.current?.abort(), [])
  useEffect(() => { if (view === 'chat') scroll.current?.scrollTo({ top: scroll.current.scrollHeight }) }, [turns, view])

  async function send(event: FormEvent) {
    event.preventDefault()
    const message = text.trim()
    if (!message || busy) return
    const id = ++nextId.current
    const request = new AbortController()
    controller.current = request
    setBusy(true); setView('chat'); setText(''); setFile(null)
    setTurns((current) => [...current, { id, message, fileName: file?.name ?? null, progress: [], thinking: '', result: null, error: '', running: true }])
    const update = (change: (turn: Turn) => Turn) => setTurns((current) => current.map((turn) => turn.id === id ? change(turn) : turn))
    try {
      await streamChat({ message, file, templateKey: selected?.object_key ?? null, previousTaskId }, request.signal, ({ event: kind, data }) => {
        if (kind === 'progress' && typeof data.message === 'string') update((turn) => ({ ...turn, progress: [...turn.progress, data.message as string] }))
        if (kind === 'thinking' && typeof data.text === 'string') update((turn) => ({ ...turn, thinking: turn.thinking + data.text }))
        if (kind === 'outline_draft' && data.outline) { setOutline(data.outline as Outline); setDraft(true); setNotice('') }
        if (kind === 'error') update((turn) => ({ ...turn, error: typeof data.message === 'string' ? data.message : '处理失败。', running: false }))
        if (kind === 'result') {
          const result = data as unknown as ChatResult
          setPreviousTaskId(result.task_id)
          update((turn) => ({ ...turn, result, running: false }))
          if (result.outline) { setOutline(result.outline); setDraft(false); setNotice(result.notice); setView('outline') }
          else { setOutline(null); setDraft(false); setView('chat') }
        }
      })
    } catch (error) {
      update((turn) => ({ ...turn, running: false, error: request.signal.aborted ? '已停止本次处理。' : error instanceof Error ? error.message : '请求失败。' }))
    } finally { if (controller.current === request) { controller.current = null; setBusy(false) } }
  }

  return <main className="chat-panel"><header className="chat-header"><div className="breadcrumb"><span>工作空间</span><span>/</span><strong>新的演示文稿</strong></div><div className="header-right"><div className="view-switch" aria-label="工作区视图"><button type="button" className={view === 'chat' ? 'active' : ''} aria-pressed={view === 'chat'} onClick={() => setView('chat')}>对话</button>{outline && <button type="button" className={view === 'outline' ? 'active' : ''} aria-pressed={view === 'outline'} onClick={() => setView('outline')}>大纲{draft ? '预览' : ''}</button>}</div></div></header>
    <div ref={scroll} className="chat-scroll" hidden={view !== 'chat'}><div className="chat-content"><div className="welcome"><div className="welcome-icon"><Sparkles size={23} /></div><span className="section-kicker">YOUR IDEAS, BEAUTIFULLY TOLD</span><h1>从一个想法，<br /><em>到一个好故事。</em></h1><p>告诉我你的主题和想法，剩下的我们一起完成。</p></div>
      <div className="conversation">{turns.map((turn) => <div key={turn.id}><div className="message user-message"><div className="message-bubble">{turn.message}{turn.fileName && <div className="sent-file"><FileText size={14} />{turn.fileName}</div>}</div><span className="avatar user-avatar">Y</span></div><div className="assistant-message"><span className="avatar ai-avatar"><Sparkles size={15} /></span><div className="assistant-body"><div className="assistant-label">叙白 <span>你的创作搭档</span></div>
        {(turn.running || turn.progress.length > 0 || turn.thinking) && <div className="process-card"><div className="process-heading"><span className={turn.running ? 'working-indicator' : 'process-spinner'}><Sparkles size={14} /></span><strong>{turn.running ? '正在制作' : '处理过程'}</strong></div>{turn.progress.length > 0 && <div className="process-steps">{turn.progress.map((step, index) => <div key={index}><span>{step}</span></div>)}</div>}{turn.thinking && <details className="thinking" open><summary>思考过程</summary><p>{turn.thinking}</p></details>}</div>}
        {turn.result && <><p>{turn.result.notice}</p>{turn.result.outline_error && <p className="result-warning">大纲生成遇到问题（{turn.result.outline_error}），请检查当前草稿。</p>}{turn.result.waiting_question && <QuestionCard question={turn.result.waiting_question} />}</>}{turn.error && <p className="result-warning" role="alert">{turn.error}</p>}
      </div></div></div>)}</div></div></div>
    {view === 'outline' && outline && <OutlinePanel outline={outline} draft={draft} notice={notice} />}
    <div className="composer-wrap"><form className="composer" onSubmit={send}><textarea value={text} onChange={(event) => setText(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} placeholder="说说你的想法，或者继续补充资料…" aria-label="输入消息" rows={2} />{file && <div className="file-list"><span><FileText size={13} />{file.name}<button type="button" aria-label={`移除 ${file.name}`} onClick={() => setFile(null)}><X size={13} /></button></span></div>}<div className="composer-actions"><div><input ref={fileInput} type="file" accept=".txt,.md,.pdf,.doc,.docx,.xlsx,.pptx" hidden onChange={(event) => { setFile(event.target.files?.[0] ?? null); event.target.value = '' }} /><button type="button" className="tool-button" onClick={() => fileInput.current?.click()}><Paperclip size={16} /><span>添加附件（一个）</span></button></div>{busy ? <Button type="button" size="icon" aria-label="停止处理" onClick={() => controller.current?.abort()}><Square size={14} /></Button> : <Button type="submit" size="icon" aria-label="发送消息" disabled={!text.trim()}><ArrowUp size={17} /></Button>}</div></form><div className="composer-caption"><span>已选模板：{selected?.file_name ?? '未选择'}</span><span>内容由 AI 生成，请注意核实重要信息</span></div></div>
  </main>
}

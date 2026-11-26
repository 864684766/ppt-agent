import { useRef, useState, type FormEvent } from 'react'
import { ArrowUp, Check, FileText, Globe2, MessageCircle, Paperclip, Plus, Sparkles, X } from 'lucide-react'
import { Button } from './ui/button'
import { OutlinePanel } from './OutlinePanel'
import type { Template } from '../data/demo'

type Message = { id: number; text: string; files: string[] }
export function ChatWorkspace({ selected, isNewSession }: { selected: Template; isNewSession: boolean }) {
  const [text, setText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [answer, setAnswer] = useState('')
  const [submittedAnswer, setSubmittedAnswer] = useState('')
  // 示例大纲已就绪；真实接入时应由后端结果驱动视图切换。
  const [view, setView] = useState<'chat' | 'outline'>(isNewSession ? 'chat' : 'outline')
  const fileInput = useRef<HTMLInputElement>(null)
  function send(event: FormEvent) {
    event.preventDefault()
    if (!text.trim() && !files.length) return
    setMessages((previous) => [...previous, { id: Date.now(), text: text.trim(), files: files.map((file) => file.name) }])
    setText(''); setFiles([])
  }
  return <main className="chat-panel"><header className="chat-header"><div className="breadcrumb"><span>工作空间</span><span>/</span><strong>新的演示文稿</strong></div><div className="header-right"><div className="view-switch" aria-label="工作区视图"><button type="button" className={view === 'chat' ? 'active' : ''} aria-pressed={view === 'chat'} onClick={() => setView('chat')}>对话</button>{!isNewSession && <button type="button" className={view === 'outline' ? 'active' : ''} aria-pressed={view === 'outline'} onClick={() => setView('outline')}>大纲</button>}</div><span className="demo-badge"><i />静态演示</span><span className="header-avatar">Y</span></div></header>
    <div className="chat-scroll" hidden={view !== 'chat'}><div className="chat-content"><div className="welcome"><div className="welcome-icon"><Sparkles size={23} /></div><span className="section-kicker">YOUR IDEAS, BEAUTIFULLY TOLD</span><h1>从一个想法，<br /><em>到一个好故事。</em></h1><p>告诉我你的主题和想法，剩下的我们一起完成。</p></div>
      <div className="conversation">{!isNewSession && <><div className="day-label"><span />今天，开始创作<span /></div><div className="message user-message"><div className="message-bubble">帮我做一份关于「AI 时代的工作方式变革」的分享，希望简洁、有启发性。</div><span className="avatar user-avatar">Y</span></div>
        <div className="assistant-message"><span className="avatar ai-avatar"><Sparkles size={15} /></span><div className="assistant-body"><div className="assistant-label">叙白 <span>你的创作搭档</span></div><p>很棒的主题！我会先梳理核心观点，再把它们组织成一个清晰、有节奏的故事。</p><div className="process-card"><div className="process-heading"><span className="process-spinner"><Sparkles size={14} /></span><strong>构思过程</strong><span className="process-status">演示内容</span></div><div className="process-steps"><div><Check size={13} /><span>理解主题与分享目标</span><small>已完成</small></div><div><Check size={13} /><span>梳理核心观点与内容结构</span><small>已完成</small></div><div><Check size={13} /><span>整理演示文稿大纲</span><small>已完成</small></div></div></div><p>我整理了一份初步大纲，可以切换到大纲查看。开始之前，还想了解一下你的听众：</p>
          <div className="question-card"><div className="question-title"><MessageCircle size={16} /><strong>需要你的想法</strong><span>示例提问</span></div><p>这次分享主要面向哪类听众？</p><div className="question-options">{['团队同事', '行业客户', '其他听众'].map((option) => <button key={option} onClick={() => setAnswer(option)} className={answer === option ? 'active' : ''}>{option}</button>)}</div><form className="answer-form" onSubmit={(event) => { event.preventDefault(); if (answer.trim()) setSubmittedAnswer(answer.trim()) }}><input aria-label="回答问题" placeholder="也可以输入你的回答…" value={answer} onChange={(event) => setAnswer(event.target.value)} /><button type="submit" aria-label="提交回答"><ArrowUp size={15} /></button></form>{submittedAnswer && <small className="answer-feedback">已记录演示回答：{submittedAnswer}</small>}</div>
        </div></div></>}
        {messages.map((message) => <div className="message user-message" key={message.id}><div className="message-bubble">{message.text}{message.files.map((file, index) => <div className="sent-file" key={`${file}-${index}`}><FileText size={14} />{file}</div>)}</div><span className="avatar user-avatar">Y</span></div>)}
        {messages.length > 0 && <div className="local-notice">消息已添加到本地演示，尚未发送至后端。</div>}
      </div></div></div>
    {view === 'outline' && <OutlinePanel selected={selected} />}
    {view === 'outline' && messages.length > 0 && <div className="outline-message-notice" role="status">消息已添加到本地演示，可切换到对话查看。</div>}
    <div className="composer-wrap"><form className="composer" onSubmit={send}><textarea value={text} onChange={(event) => setText(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} placeholder="说说你的想法，或者继续调整大纲…" aria-label="输入消息" rows={2} />{files.length > 0 && <div className="file-list">{files.map((file, index) => <span key={`${file.name}-${index}`}><FileText size={13} />{file.name}<button type="button" aria-label={`移除 ${file.name}`} onClick={() => setFiles(files.filter((_, i) => i !== index))}><X size={13} /></button></span>)}</div>}<div className="composer-actions"><div><input ref={fileInput} type="file" multiple hidden onChange={(event) => { setFiles((current) => [...current, ...Array.from(event.target.files ?? [])]); event.target.value = '' }} /><button type="button" className="tool-button" onClick={() => fileInput.current?.click()}><Paperclip size={16} /><span>添加附件</span></button><span className="tool-divider" /><span className="tool-muted"><Globe2 size={15} /> 灵感从这里开始</span></div><Button type="submit" size="icon" aria-label="发送消息" disabled={!text.trim() && !files.length}><ArrowUp size={17} /></Button></div></form><div className="composer-caption"><span><Plus size={12} /> 已选模板：{selected.name}</span><span>内容由 AI 生成，请注意核实重要信息</span></div></div>
  </main>
}

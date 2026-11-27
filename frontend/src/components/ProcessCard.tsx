import { Sparkles } from 'lucide-react'

type Props = {
  progress: string[]
  thinking: string[]
  running: boolean
  incomplete: boolean
}

/** 只负责展示已接收的事件；动画不会阻塞 SSE 解析或后续状态更新。 */
export function ProcessCard({ progress, thinking, running, incomplete }: Props) {
  const title = running ? '正在制作' : incomplete ? '处理未完成' : '处理完成'
  return <div className="process-card">
    <div className="process-heading"><span className="process-spinner"><Sparkles size={14} /></span><strong>{title}</strong></div>
    {progress.length > 0 && <div className="process-steps">{progress.map((step, index) => {
      const active = running && index === progress.length - 1
      return <div key={index}><span className={active ? 'progress-current' : undefined} aria-label={step}>
        {Array.from(step, (character, characterIndex) => <span key={characterIndex} aria-hidden="true" className={active ? 'progress-character' : undefined} style={active ? { animationDelay: `${characterIndex * 24}ms` } : undefined}>{character}</span>)}
      </span></div>
    })}</div>}
    {thinking.length > 0 && <details className="thinking" open><summary>思考过程 <span>模型推理</span></summary><div className="thinking-content">{thinking.map((chunk, index) => <span key={index} className={running ? 'thinking-chunk' : undefined}>{chunk}</span>)}</div></details>}
  </div>
}

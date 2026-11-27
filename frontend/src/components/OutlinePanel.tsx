import { FileText, Layers3, Sparkles } from 'lucide-react'
import type { Outline } from '../api/contracts'

export function OutlinePanel({ outline, draft, notice }: { outline: Outline; draft: boolean; notice: string }) {
  return <section className="outline-panel"><div className="panel-top"><div><span className="section-kicker">THE BIG PICTURE</span><h2>内容大纲</h2></div><span className="outline-icon"><Layers3 size={17} /></span></div>
    <p className="panel-description">{draft ? '正在整理，以下内容为预览。' : '根据已收集的资料整理。'}</p>
    <div className="outline-summary"><div className="summary-icon"><FileText size={18} /></div><div><strong>{outline.title}</strong><span>{draft ? '预览草稿' : '本轮结果'} · {outline.slides.length} 页</span></div></div>
    <div className="outline-list">{outline.slides.map((slide, index) => <div className="outline-item" key={index}><div className="outline-index">{String(index + 1).padStart(2, '0')}</div><div className="outline-copy"><div><strong>{slide.title}</strong><span className="outline-tag">{({ cover: '封面', content: '内容', closing: '结尾' } as Record<string, string>)[slide.role] ?? slide.role}</span></div>{slide.bullets.map((bullet, i) => <p key={i}>• {bullet.content}</p>)}</div></div>)}</div>
    {notice && <div className="outline-note"><Sparkles size={16} /><p>{notice}</p></div>}
  </section>
}

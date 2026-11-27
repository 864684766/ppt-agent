import { FileText, Layers3, Sparkles } from 'lucide-react'
import type { Outline } from '../api/contracts'

export function OutlinePanel({ outline, draft, notice, onChange }: { outline: Outline; draft: boolean; notice: string; onChange: (outline: Outline) => void }) {
  // 保留页面角色及来源编号，只更新用户修改的文字。
  function updateSlide(index: number, update: (slide: Outline['slides'][number]) => Outline['slides'][number]) {
    onChange({ ...outline, slides: outline.slides.map((slide, position) => position === index ? update(slide) : slide) })
  }
  return <section className="outline-panel"><div className="panel-top"><div><span className="section-kicker">THE BIG PICTURE</span><h2>内容大纲</h2></div><span className="outline-icon"><Layers3 size={17} /></span></div>
    <p className="panel-description">{draft ? '正在生成预览，请等待本轮完成后编辑。' : '点击标题或内容即可编辑，修改仅保存在当前页面。'}</p>
    <div className="outline-summary"><div className="summary-icon"><FileText size={18} /></div><div className="outline-summary-copy"><input className="outline-input outline-title" aria-label="大纲标题" value={outline.title} readOnly={draft} onChange={(event) => onChange({ ...outline, title: event.target.value })} /><span>{draft ? '预览草稿' : '本轮结果'} · {outline.slides.length} 页</span></div></div>
    <div className="outline-list">{outline.slides.map((slide, index) => <div className="outline-item" key={index}><div className="outline-index">{String(index + 1).padStart(2, '0')}</div><div className="outline-copy"><div className="outline-slide-header"><input className="outline-input slide-title" aria-label={`第 ${index + 1} 页标题`} value={slide.title} readOnly={draft} onChange={(event) => updateSlide(index, (current) => ({ ...current, title: event.target.value }))} /><span className="outline-tag">{({ cover: '封面', content: '内容', closing: '结尾' } as Record<string, string>)[slide.role] ?? slide.role}</span></div>{slide.bullets.map((bullet, i) => <div className="outline-bullet" key={i}><span aria-hidden="true">•</span><textarea className="outline-input bullet-input" aria-label={`第 ${index + 1} 页要点 ${i + 1}`} value={bullet.content} readOnly={draft} rows={Math.max(2, bullet.content.split('\n').length)} onChange={(event) => updateSlide(index, (current) => ({ ...current, bullets: current.bullets.map((item, position) => position === i ? { ...item, content: event.target.value } : item) }))} /></div>)}</div></div>)}</div>
    {notice && <div className="outline-note"><Sparkles size={16} /><p>{notice}</p></div>}
  </section>
}

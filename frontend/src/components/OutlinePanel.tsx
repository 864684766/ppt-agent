import { ArrowUpRight, FileText, Layers3, Sparkles } from 'lucide-react'
import { outline, type Template } from '../data/demo'
import { Button } from './ui/button'

export function OutlinePanel({ selected }: { selected: Template }) {
  return <aside className="outline-panel"><div className="panel-top"><div><span className="section-kicker">THE BIG PICTURE</span><h2>内容大纲</h2></div><span className="outline-icon"><Layers3 size={17} /></span></div>
    <p className="panel-description">先理清思路，再让故事展开。</p>
    <div className="outline-summary"><div className="summary-icon"><FileText size={18} /></div><div><strong>AI 时代的工作方式变革</strong><span>演示大纲 · {outline.length} 个章节</span></div></div>
    <div className="outline-list">{outline.map((item, index) => <div className="outline-item" key={item.title}><div className="outline-index">{String(index + 1).padStart(2, '0')}</div><div className="outline-copy"><div><strong>{item.title}</strong><span className="outline-tag">{item.tag}</span></div><p>{item.detail}</p></div></div>)}</div>
    <div className="outline-note"><Sparkles size={16} /><p>大纲会随着对话逐步完善。<br /><span>你可以随时告诉我想调整的地方。</span></p></div>
    <div className="outline-bottom"><div><span>当前风格</span><strong><i className={`style-dot ${selected.style}`} />{selected.name}</strong></div><Button variant="outline" disabled title="静态演示，暂不支持生成">生成演示文稿 <ArrowUpRight size={15} /></Button><small>生成能力将在后续接入</small></div>
  </aside>
}

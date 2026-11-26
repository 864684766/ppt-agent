import { Check, PanelLeftClose, PanelLeftOpen, Plus, Sparkles } from 'lucide-react'
import { templates, type Template } from '../data/demo'

export function TemplateSidebar({ selected, onSelect, onNewSession, collapsed, onToggle }: { selected: Template; onSelect: (template: Template) => void; onNewSession: () => void; collapsed: boolean; onToggle: () => void }) {
  return <aside className={`templates-panel ${collapsed ? 'is-collapsed' : ''}`}>
    <div className="brand"><span className="brand-mark"><Sparkles size={18} /></span><span className="brand-name" aria-hidden={collapsed}>叙白 <small>STUDIO</small></span><button type="button" className="sidebar-toggle" onClick={onToggle} aria-label={collapsed ? '展开模板面板' : '折叠模板面板'} aria-expanded={!collapsed} aria-controls="template-sidebar-content">{collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}</button></div>
    <div id="template-sidebar-content" className="sidebar-content" aria-hidden={collapsed} inert={collapsed}>
    <button type="button" className="new-session" onClick={onNewSession}><Plus size={16} />新建会话</button>
    <div className="sidebar-heading"><div><span className="section-kicker">YOUR CANVAS</span><h2>选择一个起点</h2><p>好内容，值得好设计。</p></div></div>
    <div className="filter-row"><span>全部模板</span><span>{templates.length} 个模板</span></div>
    <div className="template-list">{templates.map((item) => <button key={item.id} className={`template-card ${selected.id === item.id ? 'selected' : ''}`} onClick={() => onSelect(item)} aria-pressed={selected.id === item.id}>
      <div className={`template-preview ${item.style}`}><span className="preview-eyebrow">{item.eyebrow}</span><strong>{item.title}</strong><span className="preview-footer">PRESENTATION &nbsp; / &nbsp; 01</span><i className="preview-shape" /></div>
      <div className="template-meta"><div><strong>{item.name}</strong><span>{item.category} · 演示文稿</span></div>{selected.id === item.id && <span className="selected-check"><Check size={13} /></span>}</div>
    </button>)}</div>
    <div className="sidebar-footer"><span className="avatar small-avatar">叙</span><div><strong>你的创作空间</strong><small>让每个想法都有形状</small></div><span className="footer-dots">···</span></div>
    </div>
  </aside>
}

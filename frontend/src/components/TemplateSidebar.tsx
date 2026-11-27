import { Check, PanelLeftClose, PanelLeftOpen, Plus, Sparkles } from 'lucide-react'
import type { Template } from '../api/contracts'

type Props = { templates: Template[]; selected: Template | null; onSelect: (template: Template | null) => void; loading: boolean; error: string; onRetry: () => void; onNewSession: () => void; collapsed: boolean; onToggle: () => void }
export function TemplateSidebar({ templates, selected, onSelect, loading, error, onRetry, onNewSession, collapsed, onToggle }: Props) {
  return <aside className={`templates-panel ${collapsed ? 'is-collapsed' : ''}`}>
    <div className="brand"><span className="brand-mark"><Sparkles size={18} /></span><span className="brand-name" aria-hidden={collapsed}>叙白 <small>STUDIO</small></span><button type="button" className="sidebar-toggle" onClick={onToggle} aria-label={collapsed ? '展开模板面板' : '折叠模板面板'} aria-expanded={!collapsed} aria-controls="template-sidebar-content">{collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}</button></div>
    <div id="template-sidebar-content" className="sidebar-content" aria-hidden={collapsed} inert={collapsed}>
      <button type="button" className="new-session" onClick={onNewSession}><Plus size={16} />新建会话</button>
      <div className="sidebar-heading"><div><span className="section-kicker">YOUR CANVAS</span><h2>选择一个起点</h2><p>从模板库选择，也可以暂不选择。</p></div></div>
      <div className="filter-row"><span>模板列表</span><span>{templates.length} 个模板</span></div>
      {loading && <p className="template-status">正在读取模板列表…</p>}
      {error && <div className="template-status" role="alert">{error}<button type="button" onClick={onRetry}>重新加载</button></div>}
      {!loading && !error && templates.length === 0 && <p className="template-status">模板库暂无 PPTX 文件。</p>}
      <div className="template-list">{templates.map((item, index) => <button key={item.object_key} className={`template-card ${selected?.object_key === item.object_key ? 'selected' : ''}`} onClick={() => onSelect(selected?.object_key === item.object_key ? null : item)} aria-pressed={selected?.object_key === item.object_key} title={item.object_key}>
        <div className={`template-preview ${['linen', 'ink', 'sage', 'lilac', 'peach', 'blue'][index % 6]}`}><span className="preview-eyebrow">PRESENTATION TEMPLATE</span><strong>{item.file_name.replace(/\.pptx$/i, '')}</strong><span className="preview-footer">PPTX · 模板文件</span><i className="preview-shape" /></div>
        <div className="template-meta"><div><strong>{item.file_name}</strong><span>模板文件</span></div>{selected?.object_key === item.object_key && <span className="selected-check"><Check size={13} /></span>}</div>
      </button>)}</div><div className="sidebar-footer"><span className="avatar small-avatar">叙</span><div><strong>你的创作空间</strong><small>让每个想法都有形状</small></div></div>
    </div>
  </aside>
}

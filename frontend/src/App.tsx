import { useEffect, useState } from 'react'
import { listTemplates } from './api/client'
import type { Template } from './api/contracts'
import { TemplateSidebar } from './components/TemplateSidebar'
import { ChatWorkspace } from './components/ChatWorkspace'

export default function App() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [selected, setSelected] = useState<Template | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [reload, setReload] = useState(0)
  const [session, setSession] = useState(0)
  const [collapsed, setCollapsed] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError('')
    listTemplates(controller.signal).then(setTemplates).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '模板加载失败。')
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [reload])
  return <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}><TemplateSidebar templates={templates} selected={selected} onSelect={setSelected} loading={loading} error={error} onRetry={() => setReload((value) => value + 1)} onNewSession={() => { setSelected(null); setSession((value) => value + 1) }} collapsed={collapsed} onToggle={() => setCollapsed((value) => !value)} /><ChatWorkspace key={session} selected={selected} /></div>
}

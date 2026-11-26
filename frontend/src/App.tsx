import { useState } from 'react'
import { templates } from './data/demo'
import { TemplateSidebar } from './components/TemplateSidebar'
import { ChatWorkspace } from './components/ChatWorkspace'

export default function App() {
  const [selected, setSelected] = useState(templates[0])
  const [session, setSession] = useState(0)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  function newSession() {
    setSelected(templates[0])
    setSession((current) => current + 1)
  }
  return <div className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}><TemplateSidebar selected={selected} onSelect={setSelected} onNewSession={newSession} collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed((current) => !current)} /><ChatWorkspace key={session} selected={selected} isNewSession={session > 0} /></div>
}

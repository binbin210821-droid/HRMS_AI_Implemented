import Header from './Header.jsx'
import Sidebar from './Sidebar.jsx'
import AiAssistantWidget from '../../features/ai/AiAssistantWidget.jsx'

function MainLayout({ children }) {
  return (
    <div className="min-h-screen bg-surface-page font-sans text-ink-900">
      <Header />
      <Sidebar />
      <main className="min-h-screen px-4 pb-10 pt-24 sm:px-6 md:ml-64">{children}</main>
      <AiAssistantWidget />
    </div>
  )
}

export default MainLayout

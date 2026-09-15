import { useEffect, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { useLocation } from 'react-router-dom'

import Header from './Header.jsx'
import Sidebar from './Sidebar.jsx'
import { PageTransition } from '../animations/index.js'
import AiAssistantWidget from '../../features/ai/AiAssistantWidget.jsx'

function MainLayout({ children }) {
  const location = useLocation()
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  useEffect(() => {
    setIsSidebarOpen(false)
  }, [location.pathname])

  return (
    <div className="min-h-screen bg-surface-page font-sans text-ink-900">
      <Header onOpenMenu={() => setIsSidebarOpen(true)} isMenuOpen={isSidebarOpen} />
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
      <main className="min-h-screen px-4 pb-8 pt-20 sm:px-6 md:ml-64">
        <AnimatePresence mode="wait" initial={false}>
          <PageTransition key={location.pathname}>{children}</PageTransition>
        </AnimatePresence>
      </main>
      <AiAssistantWidget />
    </div>
  )
}

export default MainLayout

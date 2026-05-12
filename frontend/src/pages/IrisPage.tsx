import { useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { AnimatedIntro } from '../components/iris/animated-intro'
import { ChatBotUI } from '../components/iris/chat-bot-ui'

export default function IrisPage() {
  const [showIntro, setShowIntro] = useState(true)
  return (
    <main className="h-screen w-screen overflow-hidden">
      <AnimatePresence mode="wait">
        {showIntro
          ? <AnimatedIntro key="intro" onComplete={() => setShowIntro(false)} />
          : <ChatBotUI key="chat" />
        }
      </AnimatePresence>
    </main>
  )
}
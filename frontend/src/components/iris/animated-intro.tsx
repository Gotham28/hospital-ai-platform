
import { useState, useEffect, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ChatMessage } from "./chat-message"
import { TypingIndicator } from "./typing-indicator"

const LOGO_URL = "/logonewiris.png"

const demoConversation = [
  { isUser: true, message: "Is Dr. Surendran available today?" },
  { isUser: false, message: "Yes! Dr. Surendran is available today from 9am to 1pm 😊" },
  { isUser: true, message: "Can I book an appointment?" },
  { isUser: false, message: "Of course! Just tell me your name and preferred time 🗓️" },
  { isUser: true, message: "What are the OPD timings?" },
  { isUser: false, message: "OPD is open Monday to Saturday, 8am to 6pm. Emergency is 24/7 🏥" },
]

interface AnimatedIntroProps {
  onComplete: () => void
}

export function AnimatedIntro({ onComplete }: AnimatedIntroProps) {
  const [phase, setPhase] = useState<"logo" | "text" | "chat" | "transition" | "complete">("logo")
  const [visibleMessages, setVisibleMessages] = useState<typeof demoConversation>([])
  const [showTyping, setShowTyping] = useState(false)
  const [showCTA, setShowCTA] = useState(false)
  const chatContainerRef = useRef<HTMLDivElement>(null)

  // Phase transitions
  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = []


    // Logo animation complete, show text
    timers.push(setTimeout(() => setPhase("text"), 1800))

    // Text shown, start chat demo
    timers.push(setTimeout(() => setPhase("chat"), 3500))

    return () => timers.forEach(clearTimeout)
  }, [])

  // Chat demo sequence
  useEffect(() => {
    if (phase !== "chat") return

    let messageIndex = 0
    const showNextMessage = () => {
      if (messageIndex >= demoConversation.length) {
        setTimeout(() => setShowCTA(true), 300)
        setTimeout(() => setPhase("transition"), 2000)
        return
      }

      const currentMsg = demoConversation[messageIndex]

      if (!currentMsg.isUser) {
        // Show typing indicator before AI message
        setShowTyping(true)
        setTimeout(() => {
          setShowTyping(false)
          setVisibleMessages((prev) => [...prev, currentMsg])
          messageIndex++
          setTimeout(showNextMessage, 500)
        }, 800)
      } else {
        setVisibleMessages((prev) => [...prev, currentMsg])
        messageIndex++
        setTimeout(showNextMessage, 400)
      }
    }

    const startTimer = setTimeout(showNextMessage, 500)
    return () => clearTimeout(startTimer)
  }, [phase])

  // Auto-scroll chat
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight
    }
  }, [visibleMessages, showTyping])

  // Transition to main app
  useEffect(() => {
    if (phase === "transition") {
      setTimeout(onComplete, 1500)
    }
  }, [phase, onComplete])




  return (
    <motion.div
      className="fixed inset-0 bg-gradient-to-b from-[#0f172a] to-[#1E40AF] flex flex-col items-center justify-center overflow-hidden z-50"
      animate={phase === "transition" ? { scale: 1.1, opacity: 0 } : { scale: 1, opacity: 1 }}
      transition={{ duration: 1, ease: "easeInOut" }}
    >
      {/* Logo section */}
      <motion.div
        className="flex flex-col items-center"
        animate={
          phase === "chat" || phase === "transition"
            ? { scale: 0.5, y: -180, opacity: phase === "transition" ? 0 : 1 }
            : { scale: 1, y: 0 }
        }
        transition={{ duration: 0.8, type: "spring", stiffness: 100 }}
      >
        {/* Animated IRIS Logo Image */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ 
            opacity: 1, 
            y: 0 
          }}
          transition={{ 
            duration: 1.2, 
            ease: [0.25, 0.46, 0.45, 0.94]
          }}
          className="relative"
        >
          {/* Subtle glow effect behind logo */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.15 }}
            transition={{ duration: 1.5, delay: 0.5 }}
            className="absolute inset-0 bg-white rounded-3xl blur-2xl -z-10"
            style={{ transform: "scale(1.2)" }}
          />
          
          {/* Main logo image */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1, delay: 0.3 }}
            className="bg-white rounded-xl p-6 shadow-[0_4px_40px_rgba(255,255,255,0.1)]"
          >
          <img
            src={LOGO_URL}
            alt="IRIS - Institute for Rheumatology and Immunology Sciences"
            className="object-contain"
            style={{ width: 300, height: 108 }}
          />
          </motion.div>
        </motion.div>

        <AnimatePresence>
          {(phase === "text" || phase === "chat" || phase === "transition") && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.8 }}
              className="mt-6 text-center"
            >
              <motion.p
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, duration: 0.8 }}
                className="text-[#93c5fd] text-sm md:text-base tracking-wide"
              >
                Compassionate Care. Intelligent Support.
              </motion.p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Chat demo section */}
      <AnimatePresence>
        {(phase === "chat" || phase === "transition") && (
          <motion.div
            initial={{ y: 300, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ scale: 1.5, opacity: 0 }}
            transition={{ duration: 0.8, type: "spring", stiffness: 100 }}
            className="absolute bottom-0 left-0 right-0 h-[65vh] flex flex-col items-center px-4"
          >
            {/* Phone frame */}
            <div className="relative w-full max-w-sm bg-[#0f172a] rounded-t-[2.5rem] border-4 border-gray-700 shadow-2xl overflow-hidden h-full">
              {/* Phone notch */}
              <div className="absolute top-2 left-1/2 -translate-x-1/2 w-24 h-5 bg-black rounded-full z-10" />

              {/* Chat header */}
              <div className="bg-[#1E40AF] px-4 py-4 pt-8 flex items-center gap-3">
                <div className="bg-white rounded-lg p-1">
                  <img
                    src={LOGO_URL}
                    alt="IRIS"
                    width={80}
                    height={28}
                    className="object-contain"
                  />
                </div>
                <span className="text-white font-semibold">Iris AI</span>
              </div>

              {/* Chat messages */}
              <div
                ref={chatContainerRef}
                className="bg-[#EFF6FF] h-[calc(100%-8rem)] overflow-y-auto p-4 space-y-3 scroll-smooth"
              >
                {visibleMessages.map((msg, i) => (
                  <ChatMessage key={i} message={msg.message} isUser={msg.isUser} isDemo />
                ))}
                {showTyping && <TypingIndicator />}
              </div>

              {/* Input bar placeholder */}
              <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-3 flex items-center gap-2">
                <div className="flex-1 bg-gray-100 rounded-full px-4 py-2 text-sm text-gray-400">
                  Type a message...
                </div>
                <div className="w-10 h-10 bg-[#1E40AF] rounded-full flex items-center justify-center">
                  <svg
                    className="w-5 h-5 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                    />
                  </svg>
                </div>
              </div>

              {/* CTA overlay */}
              <AnimatePresence>
                {showCTA && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 bg-[#1E40AF]/80 backdrop-blur-sm flex items-center justify-center"
                  >
                    <motion.p
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ type: "spring", stiffness: 300 }}
                      className="text-white text-xl md:text-2xl font-bold text-center px-6"
                    >
                      Ask Iris AI anything →
                    </motion.p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

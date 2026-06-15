import { useState, useRef, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ChatMessage } from "./chat-message"
import { TypingIndicator } from "./typing-indicator"

const LOGO_URL = "D:\\Hospital\\hospital-ai-platform\\frontend\\public\\logonewiris.png"

// ── Change this to the actual Iris Hospital ID from your database ──
const IRIS_HOSPITAL_ID = 2

const BASE_URL =
  (import.meta as any).env?.VITE_API_URL ||
  "https://hospital-ai-platform.onrender.com/api/v1"

type Language = "en" | "ml"

interface Message {
  id: string
  text: string
  isUser: boolean
  isStreaming?: boolean
}

const translations = {
  en: {
    title: "Iris AI",
    placeholder: "Type your message...",
    suggestions: ["Doctor availability", "Book appointment", "Pharmacy", "Lab tests"],
    empty: "Start a conversation with Iris AI",
    micError: "Microphone not supported on this browser.",
    connError: "Connection error. Please try again.",
  },
  ml: {
    title: "ഐറിസ് AI",
    placeholder: "നിങ്ങളുടെ സന്ദേശം ടൈപ്പ് ചെയ്യുക...",
    suggestions: ["ഡോക്ടർ ലഭ്യത", "അപ്പോയിന്റ്മെന്റ് ബുക്ക്", "ഫാർമസി", "ലാബ് ടെസ്റ്റുകൾ"],
    empty: "ഐറിസ് AI-യുമായി സംഭാഷണം ആരംഭിക്കുക",
    micError: "ഈ ബ്രൗസറിൽ മൈക്ക് പ്രവർത്തിക്കുന്നില്ല.",
    connError: "കണക്ഷൻ പ്രശ്‌നം. വീണ്ടും ശ്രമിക്കൂ.",
  },
}

function getSessionToken(): string {
  const key = "irisSessionToken"
  let token = sessionStorage.getItem(key)
  if (!token) {
    token = crypto.randomUUID()
    sessionStorage.setItem(key, token)
  }
  return token
}

export function ChatBotUI() {
  const [language, setLanguage] = useState<Language>("en")
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState("")
  const [isTyping, setIsTyping] = useState(false)
  const [isMicActive, setIsMicActive] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)

  const chatContainerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const speechRecogRef = useRef<any>(null)
  const abortRef = useRef<AbortController | null>(null)
  const languageRef = useRef(language)

  useEffect(() => { languageRef.current = language }, [language])

  const t = translations[language]

  // Auto-scroll to bottom
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight
    }
  }, [messages, isTyping])

  // ── SEND MESSAGE WITH REAL STREAMING BACKEND ─────────────────────────────
  const handleSend = useCallback(async (overrideText?: string) => {
    const text = (overrideText ?? inputValue).trim()
    if (!text || isStreaming) return

    abortRef.current?.abort()
    abortRef.current = new AbortController()

    const userMessage: Message = {
      id: Date.now().toString(),
      text,
      isUser: true,
    }

    const historySnapshot = messages
      .filter(m => !m.isStreaming)
      .map(m => ({ role: m.isUser ? "user" : "assistant", content: m.text }))

    setMessages(prev => [...prev, userMessage])
    setInputValue("")
    setIsTyping(true)
    setIsStreaming(true)

    try {
      const response = await fetch(`${BASE_URL}/ai/chat-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          hospital_id: IRIS_HOSPITAL_ID,
          language: languageRef.current,
          history: historySnapshot,
          session_token: getSessionToken(),
        }),
        signal: abortRef.current.signal,
      })

      if (!response.ok || !response.body) throw new Error("Stream failed")

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""
      const streamId = (Date.now() + 1).toString()

      setIsTyping(false)
      setMessages(prev => [...prev, { id: streamId, text: "", isUser: false, isStreaming: true }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split("\n\n")
        buffer = frames.pop() ?? ""
        for (const frame of frames) {
          if (!frame.startsWith("data: ")) continue
          const payload = frame.slice(6)
          if (payload === "[DONE]") {
            setMessages(prev =>
              prev.map(m => m.id === streamId ? { ...m, isStreaming: false } : m)
            )
            break
          }
          try {
            const chunk = JSON.parse(payload)
            setMessages(prev =>
              prev.map(m => m.id === streamId ? { ...m, text: m.text + chunk } : m)
            )
          } catch { /* skip malformed chunks */ }
        }
      }
    } catch (err: any) {
      if (err?.name === "AbortError") return
      setIsTyping(false)
      setMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          text: translations[languageRef.current].connError,
          isUser: false,
        },
      ])
    } finally {
      setIsStreaming(false)
      setIsTyping(false)
    }
  }, [inputValue, isStreaming, messages])

  // ── SUGGESTION CHIPS ──────────────────────────────────────────────────────
  const handleSuggestionClick = (suggestion: string) => {
    handleSend(suggestion)
  }

  // ── KEYBOARD ──────────────────────────────────────────────────────────────
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // ── MIC — Web Speech API with graceful fallback message ───────────────────
  const toggleMic = useCallback(() => {
    if (isMicActive) {
      speechRecogRef.current?.stop()
      speechRecogRef.current = null
      setIsMicActive(false)
      return
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition

    if (!SpeechRecognition) {
      alert(translations[languageRef.current].micError)
      return
    }

    const recog = new SpeechRecognition()
    recog.lang = languageRef.current === "ml" ? "ml-IN" : "en-IN"
    recog.interimResults = false
    recog.maxAlternatives = 1
    speechRecogRef.current = recog
    setIsMicActive(true)

    recog.onresult = (e: any) => {
      const transcript = e.results[0]?.[0]?.transcript?.trim()
      setIsMicActive(false)
      speechRecogRef.current = null
      if (transcript) {
        handleSend(transcript)
      }
    }
    recog.onerror = () => {
      setIsMicActive(false)
      speechRecogRef.current = null
    }
    recog.onend = () => {
      setIsMicActive(false)
      speechRecogRef.current = null
    }
    recog.start()
  }, [isMicActive, handleSend])

  // ── RENDER ────────────────────────────────────────────────────────────────
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
      // FIX: added w-full overflow-hidden to prevent any child from blowing out layout
      className="h-screen w-full max-w-full overflow-x-hidden flex flex-col bg-[#EFF6FF]"

    >
      {/* Header */}
      <header className="bg-[#1E40AF] px-4 py-4 flex items-center justify-between shadow-lg relative flex-shrink-0">
        <div
          className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[#3B82F6] to-transparent opacity-50"
          style={{ boxShadow: "0 0 20px 5px rgba(59, 130, 246, 0.3)" }}
        />
        {/* FIX: min-w-0 + overflow-hidden so the left side shrinks instead of pushing toggle off-screen */}
        <div className="flex items-center gap-3 min-w-0 overflow-hidden">
          <div className="bg-white rounded-lg p-1.5 flex-shrink-0">
            <img
              src={LOGO_URL}
              alt="IRIS"
              // FIX: reduced logo width from 100→80 so it fits better on narrow screens
              style={{ width: 80, height: 32 }}
              className="object-contain"
            />
          </div>
          {/* FIX: truncate so long titles don't overflow */}
          <span className="text-white font-semibold text-lg truncate">
            {t.title}
          </span>
        </div>
        {/* FIX: flex-shrink-0 ensures the language toggle is never clipped */}
        <button
          onClick={() => setLanguage(language === "en" ? "ml" : "en")}
          className="flex-shrink-0 bg-white/20 hover:bg-white/30 text-white px-3 py-1.5 rounded-full text-sm font-medium transition-colors ml-2"
        >
          {language === "en" ? "മല" : "EN"}
        </button>
      </header>

      {/* Chat area */}
      <div
        ref={chatContainerRef}
        // FIX: min-h-0 is required so flex-1 actually scrolls inside a flex column
        className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4 relative"
      >
        {/* Watermark when empty */}
        {messages.length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center opacity-20 pointer-events-none">
            <img
              src={LOGO_URL}
              alt="IRIS"
              style={{ width: 200, height: 72 }}
              className="object-contain"
            />
            <p className="mt-4 text-[#1E40AF] text-lg">{t.empty}</p>
          </div>
        )}

        {/* Messages */}
        <AnimatePresence>
          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg.text} isUser={msg.isUser} />
          ))}
        </AnimatePresence>

        {/* Typing indicator */}
        {isTyping && <TypingIndicator />}
      </div>

      {/* Suggestion chips — only shown before any conversation */}
      {messages.length === 0 && (
        <div className="px-4 pb-2 flex-shrink-0">
          {/* FIX: was "scrollbar-hide" which doesn't exist in Tailwind — changed to "no-scrollbar"
              which IS defined in index.css */}
          <div className="flex gap-2 overflow-x-auto pb-2 no-scrollbar">
            {t.suggestions.map((suggestion, i) => (
              <motion.button
                key={i}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
                onClick={() => handleSuggestionClick(suggestion)}
                className="flex-shrink-0 bg-white border border-[#3B82F6] text-[#1E40AF] px-4 py-2 rounded-full text-sm font-medium hover:bg-[#3B82F6] hover:text-white transition-colors"
              >
                {suggestion}
              </motion.button>
            ))}
          </div>
        </div>
      )}

      {/* Input area */}
      {/* FIX: flex-shrink-0 keeps the bar from being squeezed; gap-2 tightens spacing on small screens */}
      <div className="bg-white border-t border-gray-200 px-3 py-3 flex items-center gap-2 flex-shrink-0">
        <div className="flex-1 min-w-0">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={t.placeholder}
            disabled={isStreaming}
            // FIX: w-full ensures input fills available space without overflowing
            className="w-full bg-gray-100 rounded-full px-4 py-3 text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#3B82F6] transition-shadow disabled:opacity-50"
          />
        </div>

        {/* Mic button */}
        <motion.button
          onClick={toggleMic}
          // FIX: flex-shrink-0 so buttons don't shrink when input is long
          className={`relative flex-shrink-0 w-11 h-11 rounded-full flex items-center justify-center transition-colors ${
            isMicActive ? "bg-red-500" : "bg-[#1E40AF]"
          }`}
          animate={isMicActive ? { scale: [1, 1.1, 1] } : {}}
          transition={isMicActive ? { repeat: Infinity, duration: 1 } : {}}
        >
          {isMicActive && (
            <motion.div
              className="absolute w-11 h-11 rounded-full border-2 border-red-400"
              animate={{ scale: [1, 1.5], opacity: [0.8, 0] }}
              transition={{ repeat: Infinity, duration: 1 }}
            />
          )}
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
            />
          </svg>
        </motion.button>

        {/* Send button */}
        <motion.button
          onClick={() => handleSend()}
          whileTap={{ scale: 0.95 }}
          disabled={!inputValue.trim() || isStreaming}
          // FIX: flex-shrink-0 so send button is never clipped
          className="flex-shrink-0 w-11 h-11 bg-[#1E40AF] rounded-full flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[#1E3A8A] transition-colors"
        >
          <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
            />
          </svg>
        </motion.button>
      </div>
    </motion.div>
  )
}
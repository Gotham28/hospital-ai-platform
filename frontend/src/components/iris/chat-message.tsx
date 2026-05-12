
import { motion } from "framer-motion"

interface ChatMessageProps {
  message: string
  isUser: boolean
  isDemo?: boolean
}

export function ChatMessage({ message, isUser, isDemo = false }: ChatMessageProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 500, damping: 30 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[80%] ${
          isUser
            ? "bg-[#1E40AF] text-white rounded-2xl rounded-br-md"
            : "bg-white text-gray-800 rounded-2xl rounded-bl-md shadow-md"
        } px-4 py-3 ${isDemo ? "text-sm" : "text-base"}`}
      >
        {!isUser && (
          <div className="flex items-center gap-1.5 mb-1">
            <div className="w-1.5 h-1.5 bg-[#3B82F6] rounded-full animate-pulse" />
            <span className="text-xs font-medium text-[#3B82F6]">Iris AI</span>
          </div>
        )}
        <p className="leading-relaxed">{message}</p>
      </div>
    </motion.div>
  )
}

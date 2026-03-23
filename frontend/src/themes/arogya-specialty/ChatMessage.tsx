import React from 'react';
import ReactMarkdown from 'react-markdown';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  // When true, a blinking cursor is shown after the content to signal
  // that more tokens are still arriving from the stream.
  isStreaming?: boolean;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ role, content, isStreaming }) => {
  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mr-2 text-xs font-bold border border-emerald-200 shrink-0">
          A
        </div>
      )}

      <div className={`max-w-[85%] p-4 rounded-2xl shadow-sm text-sm leading-relaxed ${
        isUser
          ? 'bg-emerald-600 text-white rounded-tr-none'
          : 'bg-white border border-gray-100 text-gray-800 rounded-tl-none'
      }`}>
        <div className="prose prose-sm max-w-none prose-emerald">
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>

        {/* Blinking cursor — only shown on assistant messages while streaming.
            Implemented as a CSS animation on a small inline block so it
            sits naturally at the end of whatever text has arrived so far. */}
        {isStreaming && !isUser && (
          <span
            style={{
              display: 'inline-block',
              width: '2px',
              height: '14px',
              backgroundColor: '#059669',  /* emerald-600 */
              marginLeft: '2px',
              verticalAlign: 'middle',
              animation: 'blink 1s step-start infinite',
            }}
          />
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-gray-200 text-gray-500 flex items-center justify-center ml-2 text-xs font-bold border border-gray-300 shrink-0">
          U
        </div>
      )}

      {/* Cursor keyframes injected once — safe to repeat across renders
          because duplicate @keyframes with identical content are a no-op. */}
      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
};

export default ChatMessage;
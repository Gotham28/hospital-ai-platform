/**
 * arogya-specialty/ChatMessage.tsx
 * ─────────────────────────────────────────────────────────────────
 * AROGYA THEME — message bubble UI only.
 * All data comes from useChatCore via the parent Chat.tsx.
 *
 * Palette: Emerald green (#059669) + slate
 * ─────────────────────────────────────────────────────────────────
 */

import React from 'react';
import ReactMarkdown from 'react-markdown';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
  language?: 'en' | 'ml';
}

const ChatMessage: React.FC<ChatMessageProps> = ({
  role,
  content,
  isStreaming,
  language = 'en',
}) => {
  const isUser = role === 'user';
  const isMalayalam = language === 'ml';

  const malayalamStyle = isMalayalam
    ? { fontFamily: "'Noto Sans Malayalam', 'Manjari', 'Rachana', sans-serif", lineHeight: '1.9' }
    : {};

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>

      {/* Bot avatar */}
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mr-2 text-xs font-bold border border-emerald-200 shrink-0">
          A
        </div>
      )}

      {/* Bubble */}
      <div
        className={`max-w-[85%] p-4 rounded-2xl shadow-sm text-sm leading-relaxed ${
          isUser
            ? 'bg-emerald-600 text-white rounded-tr-none'
            : 'bg-white border border-gray-100 text-gray-800 rounded-tl-none'
        }`}
        style={malayalamStyle}
      >
        <div className="prose prose-sm max-w-none prose-emerald" style={malayalamStyle}>
          <ReactMarkdown
            components={{
              p:      ({ children }) => <p style={malayalamStyle}>{children}</p>,
              li:     ({ children }) => <li style={malayalamStyle}>{children}</li>,
              strong: ({ children }) => <strong style={malayalamStyle}>{children}</strong>,
            }}
          >
            {content}
          </ReactMarkdown>
        </div>

        {/* Streaming cursor */}
        {isStreaming && !isUser && (
          <span style={{
            display: 'inline-block', width: '2px', height: '14px',
            backgroundColor: '#059669', marginLeft: '2px',
            verticalAlign: 'middle',
            animation: 'blink 1s step-start infinite',
          }} />
        )}
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-gray-200 text-gray-500 flex items-center justify-center ml-2 text-xs font-bold border border-gray-300 shrink-0">
          U
        </div>
      )}

      <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
    </div>
  );
};

export default ChatMessage;
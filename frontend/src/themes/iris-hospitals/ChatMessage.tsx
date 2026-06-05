/**
 * iris-hospitals/ChatMessage.tsx
 * ─────────────────────────────────────────────────────────────────
 * IRIS THEME — message bubble UI only.
 * Mirrors arogya-specialty/ChatMessage.tsx.
 *
 * Palette: Indigo/Violet on dark slate
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
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center mr-2 text-xs font-bold shrink-0"
          style={{ background: 'rgba(99,102,241,0.2)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.3)' }}
        >
          I
        </div>
      )}

      {/* Bubble */}
      <div
        className="max-w-[85%] p-4 rounded-2xl shadow-sm text-sm leading-relaxed"
        style={isUser
          ? { background: 'linear-gradient(135deg, #4338ca, #6d28d9)', color: 'white', borderTopRightRadius: '4px', ...malayalamStyle }
          : { background: 'rgba(255,255,255,0.05)', color: '#e2e8f0', border: '1px solid rgba(99,102,241,0.2)', borderTopLeftRadius: '4px', ...malayalamStyle }
        }
      >
        <div className="prose prose-sm max-w-none" style={{ ...malayalamStyle, color: 'inherit' }}>
          <ReactMarkdown
            components={{
              p:      ({ children }) => <p style={{ ...malayalamStyle, margin: '0 0 0.5em' }}>{children}</p>,
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
            backgroundColor: '#818cf8', marginLeft: '2px',
            verticalAlign: 'middle',
            animation: 'blink 1s step-start infinite',
          }} />
        )}
      </div>

      {/* User avatar */}
      {isUser && (
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center ml-2 text-xs font-bold shrink-0"
          style={{ background: 'rgba(255,255,255,0.1)', color: '#94a3b8', border: '1px solid rgba(255,255,255,0.1)' }}
        >
          U
        </div>
      )}

      <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
    </div>
  );
};

export default ChatMessage;

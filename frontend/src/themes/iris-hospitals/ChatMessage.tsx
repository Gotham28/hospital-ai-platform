/**
 * iris-hospitals/ChatMessage.tsx
 * ─────────────────────────────────────────────────────────────────
 * IRIS THEME — message bubble UI only, LIGHT rebuild.
 * Mirrors the approved Claude Design frames 02/03/04/06/08.
 *
 * Sender is identified by a text label above the bubble, not an
 * avatar — a deliberate design decision (frame 02's own caption).
 * ─────────────────────────────────────────────────────────────────
 */

import React from 'react';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { fadeUp } from './motion';

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

  const senderLabel = isMalayalam
    ? (isUser ? 'നിങ്ങൾ' : 'IRIS സഹായി')
    : (isUser ? 'You' : 'IRIS assistant');

  const bodyTextClass = isMalayalam ? 'font-malayalam text-iris-body-ml' : 'text-iris-body';

  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="show"
      className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} gap-[8px]`}
    >
      <div className="flex items-center gap-[8px]">
        <div className="text-iris-label uppercase tracking-[0.04em] font-semibold text-iris-text-muted">
          {senderLabel}
        </div>
        {isStreaming && !isUser && content !== '' && (
          <div className={`${isMalayalam ? 'font-malayalam' : ''} text-iris-label font-medium text-iris-accent`}>
            {isMalayalam ? 'എഴുതുന്നു' : 'writing'}
          </div>
        )}
      </div>

      <div
        className={`max-w-[88%] md:max-w-[76%] rounded-iris p-[16px] break-words ${bodyTextClass} ${
          isUser
            ? 'bg-iris-primary text-white'
            : 'bg-iris-accent-surface text-iris-text-primary'
        }`}
      >
        <div className="prose prose-sm max-w-none [&_*]:!m-0 [&_p+p]:!mt-[8px]" style={{ color: 'inherit' }}>
          <ReactMarkdown
            components={{
              p:      ({ children }) => <p>{children}</p>,
              li:     ({ children }) => <li>{children}</li>,
              strong: ({ children }) => <strong>{children}</strong>,
            }}
          >
            {content}
          </ReactMarkdown>
        </div>

        {/* Streaming caret — 3px per design, lands on the last token */}
        {isStreaming && !isUser && (
          <span
            aria-hidden="true"
            className="inline-block w-[3px] h-[20px] ml-[2px] align-[-4px] rounded-[2px] bg-iris-primary iris-caret"
            style={{ animation: 'irisBlink 1s step-start infinite' }}
          />
        )}
      </div>

      <style>{`
        @keyframes irisBlink { 0%, 100% { opacity: 1 } 50% { opacity: 0 } }
        @media (prefers-reduced-motion: reduce) {
          .iris-caret { animation: none !important; opacity: 1; }
        }
      `}</style>
    </motion.div>
  );
};

export default ChatMessage;

/**
 * SharedChat.tsx
 * ─────────────────────────────────────────────────────────────────
 * Shared chat UI shell used by themes that want the default
 * structure without writing their own Chat component from scratch.
 *
 * The component is UNSTYLED by design — it emits semantic class
 * names that each theme's CSS file targets.  Themes that need
 * richer customisation (e.g. Arogya with voice/mic and Malayalam)
 * should write their own Chat.tsx instead and use useChatCore().
 *
 * Class names emitted (for CSS targeting):
 *   .shared-chat-container
 *   .shared-chat-messages
 *   .shared-chat-empty-state
 *   .shared-chat-message-row  (.is-user / .is-bot)
 *   .shared-chat-bubble       (.is-user / .is-bot)
 *   .shared-chat-loading
 *   .shared-chat-input-area
 *   .shared-chat-input
 *   .shared-chat-send-btn
 * ─────────────────────────────────────────────────────────────────
 */

import React from 'react';
import { useChatCore } from './ChatCore';

interface SharedChatProps {
  hospitalId: number | string;
}

export const SharedChat: React.FC<SharedChatProps> = ({ hospitalId }) => {
  const {
    messages,
    isStreaming,
    inputText,
    setInputText,
    handleSend,
    scrollRef,
  } = useChatCore(String(hospitalId));

  return (
    <div className="shared-chat-container flex flex-col h-full w-full overflow-hidden">

      {/* Messages */}
      <div className="shared-chat-messages flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="shared-chat-empty-state opacity-50 flex justify-center items-center h-full">
            How can I help you today?
          </div>
        )}

        {messages.map((msg, idx) => {
          const isUser = msg.role === 'user';
          return (
            <div
              key={idx}
              className={`shared-chat-message-row flex w-full ${isUser ? 'justify-end is-user' : 'justify-start is-bot'}`}
            >
              <div className={`shared-chat-bubble max-w-[75%] px-4 py-3 shadow-sm ${isUser ? 'is-user' : 'is-bot'}`}>
                <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
              </div>
            </div>
          );
        })}

        {isStreaming && (
          <div className="shared-chat-loading text-sm italic opacity-70">
            Thinking…
          </div>
        )}

        <div ref={scrollRef} />
      </div>

      {/* Input */}
      <div className="shared-chat-input-area p-4 border-t flex gap-2">
        <input
          type="text"
          className="shared-chat-input flex-1 px-4 py-2 outline-none"
          placeholder="Type your message…"
          value={inputText}
          onChange={e => setInputText(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          disabled={isStreaming}
        />
        <button
          className="shared-chat-send-btn px-6 py-2 transition-transform active:scale-95"
          onClick={() => handleSend()}
          disabled={isStreaming || !inputText.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
};
import React from 'react';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ role, content }) => {
  const isUser = role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[90%] p-3 rounded-xl text-sm ${
        isUser ? 'bg-emerald-600 text-white rounded-tr-none' : 'bg-white border shadow-sm rounded-tl-none'
      }`}>
        {content}
      </div>
    </div>
  );
};

export default ChatMessage;
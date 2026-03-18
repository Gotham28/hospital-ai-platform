import React from 'react';
import ReactMarkdown from 'react-markdown'; // Run: npm install react-markdown

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ role, content }) => {
  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      {/* Avatar Icons make it feel more "human" */}
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mr-2 text-xs font-bold border border-emerald-200">
          A
        </div>
      )}

      <div className={`max-w-[85%] p-4 rounded-2xl shadow-sm text-sm leading-relaxed ${
        isUser 
          ? 'bg-emerald-600 text-white rounded-tr-none' 
          : 'bg-white border border-gray-100 text-gray-800 rounded-tl-none'
      }`}>
        {/* We use ReactMarkdown so bold text and lists actually show up */}
        <div className="prose prose-sm max-w-none prose-emerald">
           <ReactMarkdown>{content}</ReactMarkdown>
        </div>
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-gray-200 text-gray-500 flex items-center justify-center ml-2 text-xs font-bold border border-gray-300">
          U
        </div>
      )}
    </div>
  );
};

export default ChatMessage;
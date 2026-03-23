import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot } from 'lucide-react';

interface ChatPreviewProps {
  hospitalId?: string;
}

interface Message {
  role: 'user' | 'ai';
  text: string;
  isStreaming?: boolean;
}

function buildHistory(messages: Message[]): { role: string; content: string }[] {
  return messages
    .filter(m => !m.isStreaming)
    .map(m => ({
      role: m.role === 'ai' ? 'assistant' : 'user',
      content: m.text,
    }));
}

function getBaseURL(): string {
  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000/api/v1'
    : 'https://hospital-ai-platform.onrender.com/api/v1';
}

const ChatPreview: React.FC<ChatPreviewProps> = ({ hospitalId }) => {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isStreaming) return;

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    const userMessage = question;
    const historySnapshot = buildHistory(messages);

    setMessages(prev => [...prev, { role: 'user', text: userMessage }]);
    setMessages(prev => [...prev, { role: 'ai', text: '', isStreaming: true }]);
    setQuestion('');
    setIsStreaming(true);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${getBaseURL()}/ai/chat-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          question: userMessage,
          hospital_id: Number(hospitalId),
          history: historySnapshot,
        }),
        signal: abortRef.current.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n');
        buffer = frames.pop() ?? '';

        for (const frame of frames) {
          if (!frame.startsWith('data: ')) continue;
          const payload = frame.slice(6);

          if (payload === '[DONE]') {
            setMessages(prev =>
              prev.map((m, i) =>
                i === prev.length - 1 ? { ...m, isStreaming: false } : m
              )
            );
            break;
          }

          if (payload.startsWith('[ERROR]')) {
            setMessages(prev =>
              prev.map((m, i) =>
                i === prev.length - 1
                  ? { ...m, text: "I'm having trouble right now. Please try again.", isStreaming: false }
                  : m
              )
            );
            break;
          }

          try {
            const tokenText = JSON.parse(payload);
            setMessages(prev =>
              prev.map((m, i) =>
                i === prev.length - 1 ? { ...m, text: m.text + tokenText } : m
              )
            );
          } catch {
            // skip malformed token
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;

      const errorMsg = (err instanceof Error && err.message.includes('401'))
        ? "Session expired. Please log in again."
        : "I'm having trouble connecting to my brain right now.";

      setMessages(prev =>
        prev.map((m, i) =>
          i === prev.length - 1 ? { ...m, text: errorMsg, isStreaming: false } : m
        )
      );
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="flex flex-col h-[500px] w-full max-w-lg border rounded-2xl bg-gray-50 shadow-inner">
      <div className="p-4 border-b bg-white rounded-t-2xl flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot className="text-blue-600" />
          <h3 className="font-bold text-gray-800">Arogya Assistant Preview</h3>
        </div>
        <span className="text-[10px] bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full font-mono">
          ID: {hospitalId}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center mt-10">
            <p className="text-sm text-gray-400">Ask a question to test the AI training for this hospital.</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] p-3 rounded-2xl text-sm ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white rounded-tr-none'
                : 'bg-white border text-gray-800 rounded-tl-none'
            }`}>
              {msg.text}
              {msg.isStreaming && (
                <span style={{
                  display: 'inline-block',
                  width: '2px',
                  height: '12px',
                  backgroundColor: '#2563eb',
                  marginLeft: '2px',
                  verticalAlign: 'middle',
                  animation: 'blink 1s step-start infinite',
                }} />
              )}
            </div>
          </div>
        ))}
        <div ref={scrollRef} />
      </div>

      <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>

      <form onSubmit={handleSendMessage} className="p-4 bg-white border-t rounded-b-2xl flex gap-2">
        <input
          className="flex-1 text-sm p-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60"
          placeholder="Ask about doctor timings..."
          value={question}
          disabled={isStreaming}
          onChange={e => setQuestion(e.target.value)}
        />
        <button
          type="submit"
          disabled={isStreaming}
          className="bg-blue-600 p-2 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  );
};

export default ChatPreview;
import React, { useState } from 'react';
import api from '../api/axios';
import { Send, Bot } from 'lucide-react';

interface ChatPreviewProps {
  hospitalId?: string;
}

const ChatPreview: React.FC<ChatPreviewProps> = ({ hospitalId }) => {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<{ role: 'user' | 'ai'; text: string }[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    const userMessage = question;
    setMessages((prev) => [...prev, { role: 'user', text: userMessage }]);
    setQuestion('');
    setLoading(true);

    try {
      // FIX: Use 'question' instead of 'message' to match ai.py
      // FIX: Wrap hospitalId in Number() to match the 'int' type in Pydantic
      const response = await api.post('/ai/chat', { 
        question: userMessage, 
        hospital_id: Number(hospitalId) 
      });
      
      // Backend returns { "answer": "..." }
      const aiResponse = response.data.answer;
      setMessages((prev) => [...prev, { role: 'ai', text: aiResponse }]);
    } catch (err: any) {
      console.error("Chat Error Detail:", err.response?.data);
      const errorMsg = err.response?.status === 401 
        ? "Session expired. Please log in again." 
        : "I'm having trouble connecting to my brain right now.";
      setMessages((prev) => [...prev, { role: 'ai', text: errorMsg }]);
    } finally {
      setLoading(false);
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
              msg.role === 'user' ? 'bg-blue-600 text-white rounded-tr-none' : 'bg-white border text-gray-800 rounded-tl-none'
            }`}>
              {msg.text}
            </div>
          </div>
        ))}
        {loading && <div className="text-xs text-gray-400 animate-pulse">Arogya is thinking...</div>}
      </div>

      <form onSubmit={handleSendMessage} className="p-4 bg-white border-t rounded-b-2xl flex gap-2">
        <input
          className="flex-1 text-sm p-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Ask about doctor timings..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button type="submit" disabled={loading} className="bg-blue-600 p-2 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
          <Send size={18} />
        </button>
      </form>
    </div>
  );
};

export default ChatPreview;
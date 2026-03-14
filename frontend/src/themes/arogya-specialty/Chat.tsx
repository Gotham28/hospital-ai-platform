// themes/arogya-specialty/Chat.tsx

import React, { useState, useEffect, useCallback, useRef } from 'react';
import SpeechRecognition, { useSpeechRecognition } from 'react-speech-recognition';
import api from '../../api/axios';
import ChatMessage from './ChatMessage';
// Added 'Send' icon:
import { Mic, MicOff, Languages, Loader2, Activity, Send } from 'lucide-react'; 

interface ChatProps {
  hospitalId: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const Chat: React.FC<ChatProps> = ({ hospitalId }) => {
  const [language, setLanguage] = useState<'en-US' | 'ml-IN'>('en-US');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [inputText, setInputText] = useState(''); // New state for text input
  const scrollRef = useRef<HTMLDivElement>(null);

  const {
    transcript,
    listening,
    resetTranscript,
    browserSupportsSpeechRecognition
  } = useSpeechRecognition();

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, transcript]);

  const handleSend = useCallback(async (text: string) => {
    if (!text.trim()) return;

    const userMessage = text.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    resetTranscript();
    setInputText(''); // Clear text bar after sending
    setIsTyping(true);

    try {
      const response = await api.post('/ai/chat', {
        question: userMessage,
        hospital_id: parseInt(hospitalId),
        language: language === 'ml-IN' ? 'ml' : 'en'
      });
      setMessages(prev => [...prev, { role: 'assistant', content: response.data.answer }]);
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Connection to Arogya failed." }]);
    } finally {
      setIsTyping(false);
    }
  }, [hospitalId, language, resetTranscript]);

  // Handle manual Enter key press
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSend(inputText);
    }
  };

  // Silence-based auto-send for voice
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (transcript && listening) {
      timer = setTimeout(() => {
        handleSend(transcript);
      }, 1200);
    }
    return () => clearTimeout(timer);
  }, [transcript, listening, handleSend]);

  const toggleMic = () => {
    if (listening) {
      SpeechRecognition.stopListening();
    } else {
      SpeechRecognition.startListening({ continuous: true, language });
    }
  };

  if (!browserSupportsSpeechRecognition) return <p>Voice features not supported.</p>;

  return (
    <div className="w-full max-w-md bg-white rounded-2xl shadow-xl overflow-hidden border border-slate-200 flex flex-col h-[550px]">
      {/* Header */}
      <div className="bg-emerald-600 p-4 text-white flex justify-between items-center shrink-0">
        <h3 className="font-bold flex items-center gap-2">
          <Activity className="w-4 h-4" /> Ask Arogya
        </h3>
        <button 
          onClick={() => setLanguage(l => l === 'en-US' ? 'ml-IN' : 'en-US')}
          className="bg-emerald-700 px-3 py-1 rounded-md text-xs flex items-center gap-1 hover:bg-emerald-800 transition-colors"
        >
          <Languages className="w-3 h-3" />
          {language === 'en-US' ? 'English' : 'മലയാളം'}
        </button>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((msg, idx) => (
          <ChatMessage key={idx} role={msg.role} content={msg.content} />
        ))}
        {transcript && (
          <div className="flex justify-end italic text-emerald-600 animate-pulse text-xs bg-emerald-50 p-2 rounded-lg">
            {transcript}...
          </div>
        )}
        {isTyping && <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />}
        <div ref={scrollRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t bg-white">
        <div className="flex items-center gap-2 mb-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder={language === 'en-US' ? "Type your message..." : "സന്ദേശം ടൈപ്പ് ചെയ്യുക..."}
            className="flex-1 bg-slate-100 border-none rounded-full px-4 py-2 text-sm focus:ring-2 focus:ring-emerald-500 outline-none"
          />
          <button 
            onClick={() => handleSend(inputText)}
            disabled={!inputText.trim()}
            className="p-2 bg-emerald-600 text-white rounded-full disabled:bg-slate-300 transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        
        <div className="flex flex-col items-center gap-1">
          <button
            onClick={toggleMic}
            className={`p-3 rounded-full transition-all ${listening ? 'bg-red-500 text-white animate-pulse shadow-lg scale-110' : 'bg-slate-100 text-emerald-600 hover:bg-emerald-50'}`}
          >
            {listening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>
          <p className="text-[9px] uppercase tracking-widest text-slate-400 font-bold">
            {listening ? "Listening..." : "Or tap to speak"}
          </p>
        </div>
      </div>
    </div>
  );
};

export default Chat;
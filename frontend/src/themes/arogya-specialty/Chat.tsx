// themes/arogya-specialty/Chat.tsx

import React, { useState, useEffect, useCallback, useRef } from 'react';
import SpeechRecognition, { useSpeechRecognition } from 'react-speech-recognition';
import api from '../../api/axios';
import ChatMessage from './ChatMessage';
// ADD 'Activity' to this list:
import { Mic, MicOff, Languages, Loader2, Activity } from 'lucide-react'; 

// ... rest of the file
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
    setIsTyping(true);

    try {
      const response = await api.post('/chat', {
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

  // Silence-based auto-send: triggers after 1200ms of no speech detected
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
      <div className="bg-emerald-600 p-4 text-white flex justify-between items-center">
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

      <div className="p-4 border-t flex flex-col items-center gap-3">
        <button
          onClick={toggleMic}
          className={`p-4 rounded-full transition-all ${listening ? 'bg-red-500 text-white animate-pulse' : 'bg-emerald-600 text-white shadow-md'}`}
        >
          {listening ? <MicOff /> : <Mic />}
        </button>
        <p className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">
          {listening ? "Detecting Silence..." : "Tap to speak"}
        </p>
      </div>
    </div>
  );
};

export default Chat;
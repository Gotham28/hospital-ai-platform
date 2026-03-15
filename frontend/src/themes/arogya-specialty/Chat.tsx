import React, { useState, useEffect, useCallback, useRef } from 'react';
import SpeechRecognition, { useSpeechRecognition } from 'react-speech-recognition';
import api from '../../api/axios';
import ChatMessage from './ChatMessage';
import { Mic, MicOff, Languages, Loader2, Activity, Send } from 'lucide-react'; 

interface ChatProps { hospitalId: string; }
interface Message { role: 'user' | 'assistant'; content: string; }

const Chat: React.FC<ChatProps> = ({ hospitalId }) => {
  const [language, setLanguage] = useState<'en-US' | 'ml-IN'>('en-US');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [inputText, setInputText] = useState('');
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

    // 1. Force the mic to STOP immediately on send
    SpeechRecognition.stopListening();
    SpeechRecognition.abortListening();
    resetTranscript(); 

    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setIsTyping(true);

    try {
      // 2. Add a 5-second timeout so the UI doesn't hang
      const response = await api.post('/ai/chat', {
        question: text,
        hospital_id: parseInt(hospitalId),
        language: language === 'ml-IN' ? 'ml' : 'en'
      }, { timeout: 5000 }); 

      setMessages(prev => [...prev, { role: 'assistant', content: response.data.answer }]);
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Arogya is having trouble. Please try again." }]);
    } finally {
      setIsTyping(false);
    }
  }, [hospitalId, language, resetTranscript]);

  // AUTO-SEND LOGIC
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (transcript && listening) {
      timer = setTimeout(() => {
        SpeechRecognition.stopListening();
        handleSend(transcript);
      }, 1500);
    }
    return () => clearTimeout(timer);
  }, [transcript, listening, handleSend]);

  const toggleMic = () => {
    if (listening) {
      SpeechRecognition.abortListening();
      return;
    }
    resetTranscript();
    SpeechRecognition.startListening({ continuous: true, language });
  };

  return (
    <div className="w-full max-w-md bg-white rounded-2xl shadow-xl overflow-hidden border border-slate-200 flex flex-col h-[600px]">
      {/* Header */}
      <div className="bg-emerald-600 p-4 text-white flex justify-between items-center shrink-0">
        <h3 className="font-bold flex items-center gap-2">
          <Activity className="w-4 h-4" /> Ask Arogya
        </h3>
        <button 
          onClick={() => setLanguage(l => l === 'en-US' ? 'ml-IN' : 'en-US')}
          className="bg-emerald-700 px-3 py-1 rounded-md text-xs flex items-center gap-1 hover:bg-emerald-800"
        >
          <Languages className="w-3 h-3" />
          {language === 'en-US' ? 'English' : 'മലയാളം'}
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((msg, idx) => (
          <ChatMessage key={idx} role={msg.role} content={msg.content} />
        ))}
        {isTyping && <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />}
        <div ref={scrollRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t bg-white">
        <div className="flex items-center gap-2 mb-4">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend(inputText)}
            placeholder={language === 'en-US' ? "Type message..." : "സന്ദേശം..."}
            className="flex-1 bg-slate-100 border-none rounded-full px-4 py-2 text-sm outline-none"
          />
          <button onClick={() => handleSend(inputText)} className="p-2 bg-emerald-600 text-white rounded-full">
            <Send className="w-4 h-4" />
          </button>
        </div>
        
        <div className="flex flex-col items-center gap-1">
          {!browserSupportsSpeechRecognition ? (
            <p className="text-[10px] text-slate-400">Voice not supported here</p>
          ) : (
            <>
              <button
                onClick={toggleMic}
                className={`p-4 rounded-full transition-all ${listening ? 'bg-red-500 text-white animate-pulse' : 'bg-slate-100 text-emerald-600'}`}
              >
                {listening ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
              </button>
              <p className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">
                {listening ? (language === 'en-US' ? "Listening..." : "ശ്രദ്ധിക്കുന്നു...") : (language === 'en-US' ? "Tap to speak" : "സംസാരിക്കുക")}
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default Chat;
import React, { useState, useEffect, useRef } from 'react';
import SpeechRecognition, { useSpeechRecognition } from 'react-speech-recognition';
import api from '../../api/axios';
import ChatMessage from './ChatMessage';
import { Mic, MicOff, Languages, Loader2, Activity, Send, Zap } from 'lucide-react';

interface ChatProps { hospitalId: string; }
interface Message { role: 'user' | 'assistant'; content: string; }

const SUGGESTIONS = {
  'en-US': ["Who is the cardiologist today?", "Where is the pharmacy?", "Visiting hours?", "Emergency contact"],
  'ml-IN': ["കാർഡിയോളജിസ്റ്റ് ആരാണ്?", "ഫാർമസി എവിടെയാണ്?", "സന്ദർശന സമയം?", "അടിയന്തര നമ്പർ"]
};

const Chat: React.FC<ChatProps> = ({ hospitalId }) => {
  const [language, setLanguage] = useState<'en-US' | 'ml-IN'>('ml-IN');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [inputText, setInputText] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  const { transcript, listening, resetTranscript, browserSupportsSpeechRecognition } = useSpeechRecognition();

  // 1. Simple, direct Send Function
  const handleSend = async (text: string) => {
    const messageToSend = text || inputText || transcript;
    if (!messageToSend.trim()) return;

    // Hard stop mic
    SpeechRecognition.stopListening();
    
    // UI Reset
    const currentText = messageToSend.trim();
    setInputText('');
    resetTranscript();

    setMessages(prev => [...prev, { role: 'user', content: currentText }]);
    setIsTyping(true);

    try {
      const response = await api.post('/ai/chat', {
        question: currentText,
        hospital_id: parseInt(hospitalId),
        language: language === 'ml-IN' ? 'ml' : 'en'
      });
      setMessages(prev => [...prev, { role: 'assistant', content: response.data.answer }]);
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Error. Please try again." }]);
    } finally {
      setIsTyping(false);
    }
  };

  // 2. Simple Toggle
  const toggleMic = () => {
    if (listening) {
      SpeechRecognition.stopListening();
    } else {
      resetTranscript();
      SpeechRecognition.startListening({ 
        continuous: true, 
        language: language 
      });
    }
  };

  // 3. Auto-send Timer (Only if transcript exists)
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (transcript && listening) {
      timer = setTimeout(() => {
        handleSend(transcript);
      }, 2500);
    }
    return () => clearTimeout(timer);
  }, [transcript, listening]);

  // 4. Welcome Message
  useEffect(() => {
    const welcome = language === 'ml-IN' 
      ? "👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**. എനിക്ക് എങ്ങനെ സഹായിക്കാനാകും?"
      : "👋 Hello! I am **Arogya**. How can I help you today?";
    setMessages([{ role: 'assistant', content: welcome }]);
  }, [language]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (!browserSupportsSpeechRecognition) {
    return <div className="p-4 text-center text-red-500 bg-red-50">Voice features not supported.</div>;
  }

  return (
    <div className="w-full max-w-md bg-white rounded-2xl shadow-xl overflow-hidden border border-slate-200 flex flex-col h-[650px]">
      {/* Header */}
      <div className="bg-emerald-600 p-4 text-white shrink-0 shadow-md">
        <div className="flex justify-between items-center">
          <h3 className="font-bold flex items-center gap-2">
            <Activity className="w-4 h-4" /> Ask Arogya
          </h3>
          <button 
            onClick={() => setLanguage(l => l === 'en-US' ? 'ml-IN' : 'en-US')}
            className="bg-emerald-700 px-3 py-1 rounded-md text-xs font-bold border border-white/20"
          >
            {language === 'en-US' ? 'English' : 'മലയാളം'}
          </button>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((msg, idx) => (
          <ChatMessage key={idx} role={msg.role} content={msg.content} />
        ))}
        
        {listening && transcript && (
          <div className="flex justify-end">
            <div className="bg-emerald-50 text-emerald-700 px-4 py-2 rounded-2xl rounded-tr-none text-sm italic border border-emerald-100 shadow-sm animate-pulse">
              {transcript}...
            </div>
          </div>
        )}

        {isTyping && (
          <div className="flex items-center gap-2 text-emerald-600 p-2 bg-white rounded-lg w-fit shadow-sm border border-slate-100">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-[10px] font-bold">Arogya is checking...</span>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* Suggestions */}
      <div className="px-4 py-2 bg-slate-50 border-t border-slate-100">
        <div className="flex gap-2 overflow-x-auto pb-2 no-scrollbar">
          {SUGGESTIONS[language].map((text, i) => (
            <button
              key={i}
              onClick={() => handleSend(text)}
              className="flex-none bg-white border border-emerald-100 text-emerald-700 text-[11px] px-3 py-1.5 rounded-full shadow-sm hover:bg-emerald-50 active:scale-95 transition-all"
            >
              <Zap className="w-3 h-3 text-amber-400 fill-amber-400" /> {text}
            </button>
          ))}
        </div>
      </div>

      {/* Input Section */}
      <div className="p-4 border-t bg-white shrink-0">
        <div className="flex items-center gap-2 mb-4">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend(inputText)}
            placeholder={language === 'en-US' ? "Ask anything..." : "ചോദിക്കൂ..."}
            className="flex-1 bg-slate-100 border-none rounded-full px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <button 
            onClick={() => handleSend(inputText)} 
            className="p-2 bg-emerald-600 text-white rounded-full hover:bg-emerald-700 transition-colors shadow-sm"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        
        <div className="flex flex-col items-center">
          <button
            type="button"
            onClick={toggleMic}
            className={`p-4 rounded-full transition-all transform active:scale-90 shadow-lg ${
              listening 
                ? 'bg-red-500 text-white animate-pulse ring-4 ring-red-100' 
                : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100'
            }`}
          >
            {listening ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
          </button>
          <p className="text-[9px] uppercase tracking-widest text-slate-400 font-black mt-2">
            {listening ? "Recording..." : (language === 'en-US' ? "Tap to speak" : "സംസാരിക്കുക")}
          </p>
        </div>
      </div>
    </div>
  );
};

export default Chat;
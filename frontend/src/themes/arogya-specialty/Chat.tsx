import React, { useState, useEffect, useCallback, useRef } from 'react';
import SpeechRecognition, { useSpeechRecognition } from 'react-speech-recognition';
import api from '../../api/axios';
import ChatMessage from './ChatMessage';
import { Mic, MicOff, Languages, Loader2, Activity, Send, Zap, Info } from 'lucide-react';

interface ChatProps { hospitalId: string; }
interface Message { role: 'user' | 'assistant'; content: string; }

// CHANGE 1: Multi-lingual Suggestion Chips
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

  // CHANGE 2: Add a Welcome Message on mount
  useEffect(() => {
    const welcome = language === 'en-US' 
      ? "👋 Hello! I am **Arogya**. I can help with doctor schedules and hospital info. Try clicking a suggestion below!"
      : "👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**. ഡോക്ടർമാരുടെ വിവരങ്ങൾക്കും ആശുപത്രി സേവനങ്ങൾക്കും ഞാൻ നിങ്ങളെ സഹായിക്കാം.";
    setMessages([{ role: 'assistant', content: welcome }]);
  }, [language]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, transcript]);

  const handleSend = useCallback(async (text: string) => {
    const messageToSend = text.trim();
    if (!messageToSend) return;

    SpeechRecognition.stopListening();
    setInputText('');
    resetTranscript();

    setMessages(prev => [...prev, { role: 'user', content: messageToSend }]);
    setIsTyping(true);

    try {
      const response = await api.post('/ai/chat', {
        question: messageToSend,
        hospital_id: parseInt(hospitalId),
        language: language === 'ml-IN' ? 'ml' : 'en'
      });
      setMessages(prev => [...prev, { role: 'assistant', content: response.data.answer }]);
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Arogya is having trouble. Please try again." }]);
    } finally {
      setIsTyping(false);
    }
  }, [hospitalId, language, resetTranscript]);

  const toggleMic = async () => {
    if (listening) {
      await SpeechRecognition.stopListening();
      return;
    }
    resetTranscript();
    await SpeechRecognition.startListening({ continuous: true, language: language });
  };

  return (
    <div className="w-full max-w-md bg-white rounded-2xl shadow-xl overflow-hidden border border-slate-200 flex flex-col h-[650px]">
      {/* Header with Live Status */}
      <div className="bg-emerald-600 p-4 text-white shrink-0">
        <div className="flex justify-between items-center mb-1">
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
        {/* CHANGE 3: Live Status Indicator */}
        <div className="flex items-center gap-1 opacity-80">
          <div className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse"></div>
          <span className="text-[9px] uppercase tracking-widest font-bold">Live Hospital Database Connected</span>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((msg, idx) => (
          <ChatMessage key={idx} role={msg.role} content={msg.content} />
        ))}
        
        {transcript && listening && (
          <div className="flex justify-end">
            <div className="bg-emerald-50 text-emerald-700 px-4 py-2 rounded-2xl rounded-tr-none text-sm italic opacity-70 border border-emerald-100">
              {transcript}...
            </div>
          </div>
        )}

        {isTyping && (
          <div className="flex items-center gap-2 text-emerald-600 p-2 bg-white rounded-lg w-fit shadow-sm border border-slate-100">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span className="text-[10px] font-bold uppercase tracking-tight">Arogya is checking...</span>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* CHANGE 4: Suggestion Chips Container */}
      <div className="px-4 py-2 bg-slate-50 border-t border-slate-100">
        <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
          {SUGGESTIONS[language].map((text, i) => (
            <button
              key={i}
              onClick={() => handleSend(text)}
              className="flex-none bg-white border border-emerald-100 text-emerald-700 text-[11px] px-3 py-1.5 rounded-full shadow-sm hover:bg-emerald-50 transition-all flex items-center gap-1"
            >
              <Zap className="w-3 h-3 text-amber-400 fill-amber-400" /> {text}
            </button>
          ))}
        </div>
      </div>

      {/* Input Area */}
      <div className="p-4 border-t bg-white shrink-0">
        <div className="flex items-center gap-2 mb-3">
          <input
            type="text"
            value={inputText || transcript}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend(inputText || transcript)}
            placeholder={language === 'en-US' ? "Type or use mic..." : "ചോദിക്കൂ..."}
            className="flex-1 bg-slate-100 border-none rounded-full px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <button 
            onClick={() => handleSend(inputText || transcript)} 
            className="p-2 bg-emerald-600 text-white rounded-full hover:bg-emerald-700 transition-shadow shadow-md shadow-emerald-100"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        
        <div className="flex flex-col items-center">
          <button
            onClick={toggleMic}
            className={`p-3 rounded-full transition-all transform active:scale-90 ${
              listening 
                ? 'bg-red-500 text-white animate-pulse shadow-lg shadow-red-200' 
                : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100'
            }`}
          >
            {listening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>
          <p className="text-[9px] uppercase tracking-widest text-slate-400 font-black mt-2">
            {listening ? "Recording..." : "Speak in " + (language === 'en-US' ? "English" : "Malayalam")}
          </p>
        </div>
      </div>
    </div>
  );
};

export default Chat;
import React, { useState, useEffect, useCallback, useRef } from 'react';
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
  // Set Malayalam as the default language
  const [language, setLanguage] = useState<'en-US' | 'ml-IN'>('ml-IN');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [inputText, setInputText] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  const { transcript, listening, resetTranscript, browserSupportsSpeechRecognition } = useSpeechRecognition();

  // Welcome Message Effect
  useEffect(() => {
    const welcome = language === 'ml-IN' 
      ? "👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**. ഡോക്ടർമാരുടെ വിവരങ്ങൾക്കും ആശുപത്രി സേവനങ്ങൾക്കും ഞാൻ നിങ്ങളെ സഹായിക്കാം. താഴെയുള്ള ബട്ടണുകൾ ഉപയോഗിച്ച് നിങ്ങൾക്ക് ചോദ്യങ്ങൾ ചോദിക്കാം."
      : "👋 Hello! I am **Arogya**. I can help with doctor schedules and hospital info. Try clicking a suggestion below!";
    
    setMessages([{ role: 'assistant', content: welcome }]);
  }, [language]);

  // Auto-scroll Effect
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, transcript]);

  // Optimized Send Logic
const handleSend = useCallback(async (text: string) => {
  const messageToSend = text.trim();
  if (!messageToSend) return;

  // 1. HARD KILL the microphone immediately
  // .stop() tells the browser to finish, .abort() cuts the power/process
  SpeechRecognition.abortListening(); 
  
  // 2. Small delay to ensure the browser UI updates the 'listening' state
  setTimeout(() => {
    resetTranscript();
    setInputText('');
  }, 100);

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

  // AUTO-SEND LOGIC: Triggers after 2 seconds of silence
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (transcript && listening) {
      timer = setTimeout(() => {
        handleSend(transcript);
      }, 2000); // 2 second silence threshold
    }
    return () => clearTimeout(timer);
  }, [transcript, listening, handleSend]);

  const toggleMic = async () => {
    if (listening) {
      await SpeechRecognition.stopListening();
      return;
    }
    resetTranscript();
    await SpeechRecognition.startListening({ 
        continuous: true, 
        language: language 
    });
  };

  return (
    <div className="w-full max-w-md bg-white rounded-2xl shadow-xl overflow-hidden border border-slate-200 flex flex-col h-[650px]">
      
      {/* Header */}
      <div className="bg-emerald-600 p-4 text-white shrink-0 shadow-md">
        <div className="flex justify-between items-center mb-1">
          <h3 className="font-bold flex items-center gap-2 text-lg">
            <Activity className="w-5 h-5" /> Ask Arogya
          </h3>
          <button 
            onClick={() => setLanguage(l => l === 'en-US' ? 'ml-IN' : 'en-US')}
            className="bg-emerald-700 px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-2 hover:bg-emerald-800 transition-all border border-emerald-500/30"
          >
            <Languages className="w-4 h-4" />
            {language === 'en-US' ? 'English' : 'മലയാളം'}
          </button>
        </div>
        <div className="flex items-center gap-1.5 opacity-90">
          <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse shadow-[0_0_8px_rgba(74,222,128,0.8)]"></div>
          <span className="text-[10px] uppercase tracking-widest font-black">Live Database Connected</span>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((msg, idx) => (
          <ChatMessage key={idx} role={msg.role} content={msg.content} />
        ))}
        
        {transcript && listening && (
          <div className="flex justify-end">
            <div className="bg-emerald-50 text-emerald-700 px-4 py-2 rounded-2xl rounded-tr-none text-sm italic opacity-80 border border-emerald-200 shadow-sm animate-in fade-in slide-in-from-right-2">
              {transcript}...
            </div>
          </div>
        )}

        {isTyping && (
          <div className="flex items-center gap-2 text-emerald-600 p-2.5 bg-white rounded-xl w-fit shadow-sm border border-slate-100 animate-pulse">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-[11px] font-bold uppercase tracking-tight">Checking records...</span>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* Suggestion Chips */}
      <div className="px-4 py-3 bg-slate-50 border-t border-slate-100">
        <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
          {SUGGESTIONS[language].map((text, i) => (
            <button
              key={i}
              onClick={() => handleSend(text)}
              className="flex-none bg-white border border-emerald-100 text-emerald-700 text-[12px] font-medium px-4 py-2 rounded-full shadow-sm hover:bg-emerald-50 hover:border-emerald-300 transition-all flex items-center gap-2 active:scale-95"
            >
              <Zap className="w-3 h-3 text-amber-500 fill-amber-500" /> {text}
            </button>
          ))}
        </div>
      </div>

      {/* Input Area */}
      <div className="p-4 border-t bg-white shrink-0">
        <div className="flex items-center gap-3 mb-4">
          <input
            type="text"
            value={inputText || transcript}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend(inputText || transcript)}
            placeholder={language === 'en-US' ? "Ask about doctors, labs..." : "ചോദിക്കൂ..."}
            className="flex-1 bg-slate-100 border-none rounded-full px-5 py-3 text-sm outline-none focus:ring-2 focus:ring-emerald-500 transition-all"
          />
          <button 
            onClick={() => handleSend(inputText || transcript)} 
            className="p-3 bg-emerald-600 text-white rounded-full hover:bg-emerald-700 transition-all shadow-lg shadow-emerald-100 active:scale-90"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
        
        {/* Voice Control Section */}
        <div className="flex flex-col items-center">
          <button
            onClick={toggleMic}
            className={`p-4 rounded-full transition-all transform active:scale-90 shadow-xl ${
              listening 
                ? 'bg-red-500 text-white animate-pulse shadow-red-200' 
                : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100'
            }`}
          >
            {listening ? <MicOff className="w-7 h-7" /> : <Mic className="w-7 h-7" />}
          </button>
          <p className="text-[10px] uppercase tracking-[0.2em] text-slate-400 font-black mt-3">
            {listening 
                ? (language === 'en-US' ? "Listening..." : "ശ്രദ്ധിക്കുന്നു...") 
                : (language === 'en-US' ? "Tap to speak English" : "സംസാരിക്കാൻ ടാപ്പ് ചെയ്യുക")}
          </p>
        </div>
      </div>
    </div>
  );
};

export default Chat;
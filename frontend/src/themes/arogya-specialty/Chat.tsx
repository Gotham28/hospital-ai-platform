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

  // Auto-scroll to bottom
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, transcript]);

  const handleSend = useCallback(async (text: string) => {
    const messageToSend = text.trim();
    if (!messageToSend) return;

    // Forcefully kill mic hardware immediately
    SpeechRecognition.stopListening();
    SpeechRecognition.abortListening();
    
    // Clear inputs
    setInputText('');
    resetTranscript();

    setMessages(prev => [...prev, { role: 'user', content: messageToSend }]);
    setIsTyping(true);

    try {
      const response = await api.post('/ai/chat', {
        question: messageToSend,
        hospital_id: parseInt(hospitalId),
        language: language === 'ml-IN' ? 'ml' : 'en'
      }, { timeout: 10000 }); // 10 second timeout for mobile/slower networks

      setMessages(prev => [...prev, { role: 'assistant', content: response.data.answer }]);
    } catch (error) {
      console.error("Chat Error:", error);
      setMessages(prev => [...prev, { role: 'assistant', content: "Arogya is having trouble. Please try again." }]);
    } finally {
      setIsTyping(false);
    }
  }, [hospitalId, language, resetTranscript]);

  // AUTO-SEND LOGIC: Sends message after 2 seconds of silence
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (transcript && listening) {
      timer = setTimeout(() => {
        handleSend(transcript);
      }, 2000);
    }
    return () => clearTimeout(timer);
  }, [transcript, listening, handleSend]);

// Force the state to update properly
const toggleMic = async () => {
  if (listening) {
    await SpeechRecognition.stopListening();
    return;
  }

  // IMPORTANT: Ensure resetTranscript is called before starting
  resetTranscript();
  
  // Explicitly mapping the exact strings the browser expects
  const currentLang = language === 'ml-IN' ? 'ml-IN' : 'en-US';

  try {
    await SpeechRecognition.startListening({ 
      continuous: true, 
      language: currentLang 
    });
    console.log("Mic started with language:", currentLang);
  } catch (err) {
    console.error("Mic failed to start:", err);
  }
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
          className="bg-emerald-700 px-3 py-1 rounded-md text-xs flex items-center gap-1 hover:bg-emerald-800 transition-colors"
        >
          <Languages className="w-3 h-3" />
          {language === 'en-US' ? 'English' : 'മലയാളം'}
        </button>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.length === 0 && (
          <div className="text-center text-slate-400 mt-10 text-sm">
            {language === 'en-US' ? "How can I help you today?" : "ഇന്ന് എനിക്ക് എങ്ങനെ സഹായിക്കാനാകും?"}
          </div>
        )}
        
{/* FIX IS HERE: Added ) before the } */}
  {messages.map((msg, idx) => (
    <ChatMessage key={idx} role={msg.role} content={msg.content} />
  ))}
        
        {/* Live Transcript Preview */}
        {transcript && listening && (
          <div className="flex justify-end">
            <div className="bg-emerald-50 text-emerald-700 px-4 py-2 rounded-2xl rounded-tr-none text-sm italic opacity-70">
              {transcript}...
            </div>
          </div>
        )}

        {isTyping && (
          <div className="flex items-center gap-2 text-emerald-600">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-xs">Arogya is thinking...</span>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t bg-white">
        <div className="flex items-center gap-2 mb-4">
          <input
            type="text"
            value={inputText || transcript} // Show transcript in input if speaking
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend(inputText || transcript)}
            placeholder={language === 'en-US' ? "Type message..." : "സന്ദേശം..."}
            className="flex-1 bg-slate-100 border-none rounded-full px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <button 
            onClick={() => handleSend(inputText || transcript)} 
            className="p-2 bg-emerald-600 text-white rounded-full hover:bg-emerald-700 transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        
        <div className="flex flex-col items-center gap-1">
          {!browserSupportsSpeechRecognition ? (
            <p className="text-[10px] text-slate-400">Voice not supported in this browser</p>
          ) : (
            <>
              <button
                onClick={toggleMic}
                className={`p-4 rounded-full transition-all transform active:scale-95 ${
                  listening 
                    ? 'bg-red-500 text-white animate-pulse shadow-lg shadow-red-200' 
                    : 'bg-slate-100 text-emerald-600 hover:bg-slate-200'
                }`}
              >
                {listening ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
              </button>
              <p className="text-[10px] uppercase tracking-widest text-slate-400 font-bold mt-1">
                {listening 
                  ? (language === 'en-US' ? "Listening..." : "ശ്രദ്ധിക്കുന്നു...") 
                  : (language === 'en-US' ? "Tap to speak" : "സംസാരിക്കുക")}
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default Chat;
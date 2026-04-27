import React, { useEffect, useRef } from 'react';
import ChatMessage from './ChatMessage';
import { Mic, MicOff, Send, Zap, Activity, Loader2, AlertCircle } from 'lucide-react';
import { useHospitalChat } from '../../hooks/useHospitalChat'; // Import the "brain"

interface ChatProps { hospitalId: string; }

const Chat: React.FC<ChatProps> = ({ hospitalId }) => {
  // Plug the UI into the brain
  const {
    language, setLanguage, messages, isStreaming, inputText, setInputText,
    micState, micError, suggestions, handleSend, toggleMic,vad
  } = useHospitalChat(hospitalId);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => { scrollRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const micBtnClass = {
    idle: 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100',
    recording: 'bg-red-500 text-white ring-4 ring-red-100 animate-pulse',
    transcribing: 'bg-emerald-600 text-white opacity-80',
  }[micState];

  const micLabel = {
    idle: vad.loading 
            ? (language === 'en' ? 'Loading AI...' : 'ലോഡുചെയ്യുന്നു...') 
            : (language === 'en' ? 'Tap to speak' : 'സംസാരിക്കുക'),
    recording: language === 'en' ? 'Listening...' : 'ശ്രദ്ധിക്കുന്നു...',
    transcribing: language === 'en' ? 'Translating...' : 'വിവർത്തനം ചെയ്യുന്നു...',
  }[micState];

  return (
    <div className="w-full max-w-md bg-white rounded-2xl shadow-xl overflow-hidden border border-slate-200 flex flex-col h-[650px]">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Malayalam:wght@400;500;700&display=swap');
        .ml-text { font-family: 'Noto Sans Malayalam', sans-serif !important; }
      `}</style>

      {/* Header (Arogya Theme Colors) */}
      <div className="bg-emerald-600 p-4 text-white shrink-0 shadow-md">
        <div className="flex justify-between items-center">
          <h3 className="font-bold flex items-center gap-2">
            <Activity className="w-4 h-4" /> Ask Arogya
          </h3>
          <button
            onClick={() => setLanguage(l => l === 'en' ? 'ml' : 'en')}
            disabled={micState !== 'idle'}
            className="bg-emerald-700 px-3 py-1 rounded-md text-xs font-bold border border-white/20 disabled:opacity-50 ml-text"
          >
            {language === 'en' ? 'English' : 'മലയാളം'}
          </button>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((msg, idx) => (
          <ChatMessage key={idx} role={msg.role} content={msg.content} isStreaming={msg.isStreaming} language={language} />
        ))}
        {isStreaming && messages[messages.length - 1]?.content === '' && (
          <div className="flex items-center gap-2 text-emerald-600 p-2 bg-white rounded-lg w-fit shadow-sm border border-slate-100">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-[10px] font-bold ml-text">
              {language === 'ml' ? 'ആരോഗ്യ പരിശോധിക്കുന്നു...' : 'Arogya is checking...'}
            </span>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* Suggestion chips */}
      <div className="px-4 py-2 bg-slate-50 border-t border-slate-100">
        <div className="flex gap-2 overflow-x-auto pb-2 no-scrollbar">
          {suggestions[language].map((text, i) => (
            <button key={i} disabled={isStreaming || micState !== 'idle'} onClick={() => handleSend(text)}
              className="flex-none bg-white border border-emerald-100 text-emerald-700 text-[11px] px-3 py-1.5 rounded-full shadow-sm hover:bg-emerald-50 active:scale-95 transition-all disabled:opacity-40 whitespace-nowrap ml-text">
              <Zap className="w-3 h-3 text-amber-400 fill-amber-400 inline mr-1" />{text}
            </button>
          ))}
        </div>
      </div>

      {/* Input + mic */}
      <div className="p-4 border-t bg-white shrink-0 space-y-3">
        {micError && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
            <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
            <p className="text-xs text-red-700 ml-text">{micError}</p>
          </div>
        )}

        <div className="flex items-center gap-2">
          <input type="text" value={inputText} onChange={e => setInputText(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !isStreaming && handleSend()}
            placeholder={language === 'en' ? 'Ask anything…' : 'ചോദിക്കൂ…'}
            disabled={isStreaming || micState !== 'idle'}
            className="flex-1 bg-slate-100 border-none rounded-full px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-60 ml-text" />
          <button onClick={() => handleSend()} disabled={isStreaming || !inputText.trim() || micState !== 'idle'}
            className="p-2 bg-emerald-600 text-white rounded-full hover:bg-emerald-700 disabled:opacity-40">
            <Send className="w-4 h-4" />
          </button>
        </div>

<div className="flex flex-col items-center">
          <button type="button" onClick={toggleMic} 
            disabled={isStreaming || micState === 'transcribing' || vad.loading}
            className={`p-4 rounded-full transition-all transform active:scale-90 shadow-lg disabled:opacity-50 flex items-center justify-center ${micBtnClass}`}
            aria-label={micLabel}>
            
            {/* Show a spinner if VAD is downloading its files */}
            {vad.loading ? <Loader2 className="w-6 h-6 animate-spin" /> : 
             micState === 'recording' ? <MicOff className="w-6 h-6" /> : 
             micState === 'transcribing' ? <Loader2 className="w-6 h-6 animate-spin" /> : 
             <Mic className="w-6 h-6" />}
             
          </button>
          <p className="text-[9px] uppercase tracking-widest text-slate-400 font-black mt-2 text-center ml-text">
             {micLabel}
          </p>
        </div>
      </div>
    </div>
  );
};

export default Chat;
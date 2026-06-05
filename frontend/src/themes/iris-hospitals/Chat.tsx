/**
 * iris-hospitals/Chat.tsx
 * ─────────────────────────────────────────────────────────────────
 * IRIS THEME — full chat widget UI (voice + text + suggestions).
 *
 * Mirrors arogya-specialty/Chat.tsx pattern.
 * ALL logic comes from useChatCore(). Zero API calls here.
 *
 * Palette: Indigo/Violet on dark slate
 * ─────────────────────────────────────────────────────────────────
 */

import 'regenerator-runtime/runtime';
import React, { useEffect, useRef } from 'react';
import { Mic, MicOff, Send, Zap, Activity, Loader2, AlertCircle } from 'lucide-react';
import ChatMessage from './ChatMessage';
import { useChatCore } from '../../components/common/ChatCore';

interface ChatProps {
  hospitalId: string;
}

type MicState = 'idle' | 'recording' | 'transcribing';
type Language = 'en' | 'ml';

interface ChatMessageData {
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
}

interface ChatCoreReturn {
  language: Language;
  setLanguage: React.Dispatch<React.SetStateAction<Language>>;
  messages: ChatMessageData[];
  isStreaming: boolean;
  inputText: string;
  setInputText: (text: string) => void;
  micState: MicState;
  micError: string | null;
  suggestions: { en: string[]; ml: string[] };
  handleSend: (text?: string) => Promise<void>;
  toggleMic: () => void;
  vadLoading: boolean;
}

const Chat: React.FC<ChatProps> = ({ hospitalId }) => {
  const {
    language, setLanguage, messages, isStreaming,
    inputText, setInputText,
    micState, micError,
    suggestions,
    handleSend, toggleMic,
    vadLoading
  } = useChatCore(hospitalId) as ChatCoreReturn;

  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Mic button appearance ──────────────────────────────────
  const micBtnClass: Record<MicState, string> = {
    idle:         'text-indigo-300 hover:bg-white/10',
    recording:    'bg-red-500 text-white ring-4 ring-red-400/30 animate-pulse',
    transcribing: 'bg-indigo-600 text-white opacity-80',
  };

  const micLabel: Record<MicState, string> = {
    idle:         vadLoading
                    ? (language === 'en' ? 'Loading AI…' : 'ലോഡുചെയ്യുന്നു…')
                    : (language === 'en' ? 'Tap to speak' : 'സംസാരിക്കുക'),
    recording:    language === 'en' ? 'Listening…'   : 'ശ്രദ്ധിക്കുന്നു…',
    transcribing: language === 'en' ? 'Translating…' : 'വിവർത്തനം ചെയ്യുന്നു…',
  };

  return (
    <div
      className="w-full max-w-md rounded-2xl shadow-2xl overflow-hidden flex flex-col h-[650px] border"
      style={{ background: '#0f172a', borderColor: 'rgba(99,102,241,0.3)' }}
    >
      {/* Malayalam font import */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Malayalam:wght@400;500;700&display=swap');
        .ml-text { font-family: 'Noto Sans Malayalam', sans-serif !important; }
        .iris-scrollbar::-webkit-scrollbar { width: 4px; }
        .iris-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .iris-scrollbar::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.3); border-radius: 2px; }
      `}</style>

      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="p-4 text-white shrink-0" style={{ background: 'linear-gradient(135deg, #4338ca, #6d28d9)' }}>
        <div className="flex justify-between items-center">
          <h3 className="font-bold flex items-center gap-2 text-sm">
            <Activity className="w-4 h-4" />
            {language === 'ml' ? 'IRIS-നോട് ചോദിക്കൂ' : 'Ask IRIS'}
          </h3>
          <button
            onClick={() => setLanguage(l => l === 'en' ? 'ml' : 'en')}
            disabled={micState !== 'idle'}
            className="px-3 py-1 rounded-md text-xs font-bold border border-white/20 disabled:opacity-50 ml-text"
            style={{ background: 'rgba(255,255,255,0.15)' }}
          >
            {language === 'en' ? 'English' : 'മലയാളം'}
          </button>
        </div>
      </div>

      {/* ── Messages ─────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 iris-scrollbar" style={{ background: '#0f172a' }}>
        {messages.map((msg, idx) => (
          <ChatMessage
            key={idx}
            role={msg.role}
            content={msg.content}
            isStreaming={msg.isStreaming}
            language={language}
          />
        ))}
        {isStreaming && messages[messages.length - 1]?.content === '' && (
          <div className="flex items-center gap-2 p-2 rounded-lg w-fit shadow-sm" style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.2)' }}>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-[10px] font-bold ml-text">
              {language === 'ml' ? 'IRIS പരിശോധിക്കുന്നു…' : 'IRIS is checking…'}
            </span>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* ── Suggestion chips ─────────────────────────────────────── */}
      <div className="px-4 py-2 border-t" style={{ background: '#0f172a', borderColor: 'rgba(99,102,241,0.2)' }}>
        <div className="flex gap-2 overflow-x-auto pb-2 no-scrollbar">
          {suggestions[language].map((text, i) => (
            <button
              key={i}
              disabled={isStreaming || micState !== 'idle'}
              onClick={() => handleSend(text)}
              className="flex-none text-[11px] px-3 py-1.5 rounded-full shadow-sm active:scale-95 transition-all disabled:opacity-40 whitespace-nowrap ml-text"
              style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.25)', color: '#a5b4fc' }}
            >
              <Zap className="w-3 h-3 inline mr-1" style={{ color: '#fbbf24', fill: '#fbbf24' }} />
              {text}
            </button>
          ))}
        </div>
      </div>

      {/* ── Input + mic ──────────────────────────────────────────── */}
      <div className="p-4 border-t shrink-0 space-y-3" style={{ background: '#0f172a', borderColor: 'rgba(99,102,241,0.2)' }}>
        {micError && (
          <div className="flex items-start gap-2 rounded-lg px-3 py-2" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)' }}>
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <p className="text-xs text-red-400 ml-text">{micError}</p>
          </div>
        )}

        <div className="flex items-center gap-2">
          <input
            type="text"
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !isStreaming && handleSend()}
            placeholder={language === 'en' ? 'Ask anything…' : 'ചോദിക്കൂ…'}
            disabled={isStreaming || micState !== 'idle'}
            className="flex-1 rounded-full px-4 py-2 text-sm outline-none disabled:opacity-60 ml-text text-white placeholder-slate-500"
            style={{ background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(99,102,241,0.25)', focusRing: 'none' }}
          />
          <button
            onClick={() => handleSend()}
            disabled={isStreaming || !inputText.trim() || micState !== 'idle'}
            className="p-2 rounded-full disabled:opacity-40 transition-all"
            style={{ background: 'linear-gradient(135deg, #4338ca, #6d28d9)', color: 'white' }}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        {/* Mic — centred below input, exactly like Arogya */}
        <div className="flex flex-col items-center">
          <button
            type="button"
            onClick={toggleMic}
            disabled={isStreaming || micState === 'transcribing' || vadLoading}
            className={`p-4 rounded-full transition-all transform active:scale-90 shadow-lg disabled:opacity-50 flex items-center justify-center ${micBtnClass[micState]}`}
            style={micState === 'idle' ? { background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)' } : {}}
            aria-label={micLabel[micState]}
          >
            {vadLoading             ? <Loader2 className="w-6 h-6 animate-spin" /> :
             micState === 'recording'    ? <MicOff className="w-6 h-6" /> :
             micState === 'transcribing' ? <Loader2 className="w-6 h-6 animate-spin" /> :
                                           <Mic className="w-6 h-6" />}
          </button>
          <p className="text-[9px] uppercase tracking-widest font-black mt-2 text-center ml-text" style={{ color: '#475569' }}>
            {micLabel[micState]}
          </p>
        </div>
      </div>
    </div>
  );
};

export default Chat;

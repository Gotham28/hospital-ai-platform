import React, { useState, useEffect, useRef, useCallback } from 'react';
import SpeechRecognition, { useSpeechRecognition } from 'react-speech-recognition';
import ChatMessage from './ChatMessage';
import { Mic, MicOff, Send, Zap, Activity, Loader2, AlertCircle } from 'lucide-react';

interface ChatProps { hospitalId: string; }

interface Message {
  role: 'user' | 'assistant';
  content: string;
  isWelcome?: boolean;
  isStreaming?: boolean;
}

type MicState = 'idle' | 'recording';

const SILENCE_THRESHOLD_MS = 1800;
const SILENCE_CHECK_INTERVAL_MS = 300;

const FALLBACK_SUGGESTIONS = {
  en: ["What can Arogya help me with?", "Which doctors are available?", "How do I contact the hospital?", "Tell me about this hospital"],
  ml: ["ആരോഗ്യ എന്തൊക്കെ സഹായിക്കും?", "ഏത് ഡോക്ടർ ഉണ്ട്?", "ആശുപത്രിയിൽ എങ്ങനെ ബന്ധപ്പെടാം?", "ഈ ആശുപത്രിയെക്കുറിച്ച് പറയൂ"],
};

// Shown while the real welcome is loading
const LOADING_WELCOME = {
  en: "👋 Hello! I am **Arogya**. Loading your hospital information…",
  ml: "👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**. ആശുപത്രി വിവരങ്ങൾ ലോഡ് ചെയ്യുന്നു…",
};

function buildHistory(messages: Message[]): { role: string; content: string }[] {
  return messages.filter(m => !m.isWelcome && !m.isStreaming).map(m => ({ role: m.role, content: m.content }));
}

function getBaseURL(): string {
  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000/api/v1'
    : 'https://hospital-ai-platform.onrender.com/api/v1';
}

const Chat: React.FC<ChatProps> = ({ hospitalId }) => {
  const [language, setLanguage] = useState<'en' | 'ml'>('ml');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [inputText, setInputText] = useState('');
  const [micState, setMicState] = useState<MicState>('idle');
  const [micError, setMicError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<{ en: string[]; ml: string[] }>(FALLBACK_SUGGESTIONS);
  // Cache welcome messages so we don't re-fetch on every language toggle
  const welcomeCache = useRef<{ en: string; ml: string } | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastTranscriptUpdateRef = useRef<number>(0);
  const transcriptRef = useRef<string>('');
  const silenceIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const autoSendingRef = useRef(false);
  const handleSendRef = useRef<((text: string) => Promise<void>) | null>(null);

  const {
    transcript,
    listening,
    resetTranscript,
    browserSupportsSpeechRecognition,
  } = useSpeechRecognition();

  // ── Fetch dynamic welcome message from backend ────────────────────────────
  useEffect(() => {
    if (!hospitalId) return;
    const token = localStorage.getItem('token');

    // Show a loading placeholder immediately
    setMessages([{ role: 'assistant', content: LOADING_WELCOME[language], isWelcome: true }]);

    if (welcomeCache.current) {
      // Already fetched — just swap language
      setMessages([{ role: 'assistant', content: welcomeCache.current[language], isWelcome: true }]);
      return;
    }

    fetch(`${getBaseURL()}/ai/welcome/${hospitalId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.en && data?.ml) {
          welcomeCache.current = { en: data.en, ml: data.ml };
          setMessages([{ role: 'assistant', content: data[language], isWelcome: true }]);
        } else {
          // Backend didn't return expected shape — use a sensible fallback
          setMessages([{
            role: 'assistant',
            content: language === 'ml'
              ? "👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**. എനിക്ക് എങ്ങനെ സഹായിക്കാനാകും?"
              : "👋 Hello! I am **Arogya**. How can I help you today?",
            isWelcome: true
          }]);
        }
      })
      .catch(() => {
        setMessages([{
          role: 'assistant',
          content: language === 'ml'
            ? "👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**. എനിക്ക് എങ്ങനെ സഹായിക്കാനാകും?"
            : "👋 Hello! I am **Arogya**. How can I help you today?",
          isWelcome: true
        }]);
      });
  // Only re-fetch when hospitalId changes; language changes are handled below
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hospitalId]);

  // ── Swap welcome language without re-fetching ─────────────────────────────
  useEffect(() => {
    setMessages(prev => {
      if (prev.length === 0) return prev;
      const first = prev[0];
      if (!first.isWelcome) return prev;
      const newContent = welcomeCache.current
        ? welcomeCache.current[language]
        : language === 'ml'
          ? "👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**. എനിക്ക് എങ്ങനെ സഹായിക്കാനാകും?"
          : "👋 Hello! I am **Arogya**. How can I help you today?";
      return [{ ...first, content: newContent }, ...prev.slice(1)];
    });
  }, [language]);

  // ── Fetch dynamic suggestions from backend ────────────────────────────────
  useEffect(() => {
    if (!hospitalId) return;
    const token = localStorage.getItem('token');
    fetch(`${getBaseURL()}/ai/suggestions/${hospitalId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.en && data?.ml) setSuggestions(data); })
      .catch(() => {});
  }, [hospitalId]);

  // ── Keep transcriptRef in sync ────────────────────────────────────────────
  useEffect(() => {
    if (transcript !== transcriptRef.current) {
      transcriptRef.current = transcript;
      lastTranscriptUpdateRef.current = Date.now();
    }
  }, [transcript]);

  // ── Silence detection ─────────────────────────────────────────────────────
  const stopSilenceDetection = useCallback(() => {
    if (silenceIntervalRef.current) {
      clearInterval(silenceIntervalRef.current);
      silenceIntervalRef.current = null;
    }
  }, []);

  const startSilenceDetection = useCallback(() => {
    stopSilenceDetection();
    lastTranscriptUpdateRef.current = Date.now();
    silenceIntervalRef.current = setInterval(() => {
      const silentFor = Date.now() - lastTranscriptUpdateRef.current;
      const hasContent = transcriptRef.current.trim().length > 0;
      if (hasContent && silentFor >= SILENCE_THRESHOLD_MS) {
        stopSilenceDetection();
        if (!autoSendingRef.current) {
          autoSendingRef.current = true;
          const captured = transcriptRef.current.trim();
          SpeechRecognition.abortListening();
          setMicState('idle');
          if (handleSendRef.current) handleSendRef.current(captured);
        }
      }
    }, SILENCE_CHECK_INTERVAL_MS);
  }, [stopSilenceDetection]);

  useEffect(() => () => { stopSilenceDetection(); abortRef.current?.abort(); }, [stopSilenceDetection]);

  // ── Restart listening when browser auto-stops (continuous: false) ─────────
  useEffect(() => {
    if (micState === 'recording' && !listening && !autoSendingRef.current) {
      SpeechRecognition.startListening({ continuous: false, language: language === 'ml' ? 'ml-IN' : 'en-US' });
    }
  }, [listening, micState, language]);

  // ── Mic toggle ────────────────────────────────────────────────────────────
  const toggleMic = useCallback(async () => {
    setMicError(null);

    if (micState === 'idle') {
      if (navigator.permissions) {
        try {
          const result = await navigator.permissions.query({ name: 'microphone' as PermissionName });
          if (result.state === 'denied') {
            setMicError(language === 'ml'
              ? 'മൈക്രോഫോൺ ആക്സസ് തടഞ്ഞിരിക്കുന്നു. ബ്രൗസർ സെറ്റിംഗ്സിൽ അനുവദിക്കൂ.'
              : 'Microphone access is blocked. Please allow it in your browser settings and refresh.');
            return;
          }
        } catch { /* permissions API not supported */ }
      }
      try {
        resetTranscript();
        transcriptRef.current = '';
        lastTranscriptUpdateRef.current = Date.now();
        autoSendingRef.current = false;
        setInputText('');
        SpeechRecognition.startListening({ continuous: false, language: language === 'ml' ? 'ml-IN' : 'en-US' });
        setMicState('recording');
        startSilenceDetection();
      } catch {
        setMicError(language === 'ml'
          ? 'മൈക്രോഫോൺ ആക്സസ് ലഭ്യമല്ല. ക്രോം ബ്രൗസർ ഉപയോഗിക്കൂ.'
          : 'Could not access microphone. Please use Chrome and ensure mic permission is granted.');
      }
    } else if (micState === 'recording') {
      stopSilenceDetection();
      autoSendingRef.current = false;
      SpeechRecognition.abortListening();
      resetTranscript();
      transcriptRef.current = '';
      setInputText('');
      setMicState('idle');
    }
  }, [micState, language, startSilenceDetection, stopSilenceDetection, resetTranscript]);

  // ── Send (streaming) ──────────────────────────────────────────────────────
  const handleSend = useCallback(async (text: string) => {
    const msg = (text || inputText).trim();
    if (!msg || isStreaming) return;

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    stopSilenceDetection();
    SpeechRecognition.abortListening();
    resetTranscript();
    transcriptRef.current = '';
    autoSendingRef.current = false;
    setInputText('');
    setMicState('idle');
    setMicError(null);

    const historySnapshot = buildHistory(messages);
    setMessages(prev => [...prev, { role: 'user', content: msg }]);
    setMessages(prev => [...prev, { role: 'assistant', content: '', isStreaming: true }]);
    setIsStreaming(true);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${getBaseURL()}/ai/chat-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          question: msg,
          hospital_id: parseInt(hospitalId),
          language,
          history: historySnapshot,
        }),
        signal: abortRef.current.signal,
      });

      if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n');
        buffer = frames.pop() ?? '';
        for (const frame of frames) {
          if (!frame.startsWith('data: ')) continue;
          const payload = frame.slice(6);
          if (payload === '[DONE]') {
            setMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, isStreaming: false } : m));
            break;
          }
          if (payload.startsWith('[ERROR]')) {
            setMessages(prev => prev.map((m, i) => i === prev.length - 1
              ? { ...m, content: language === 'ml' ? 'ക്ഷമിക്കണം, ഒരു പ്രശ്‌നം ഉണ്ടായി. വീണ്ടും ശ്രമിക്കൂ.' : 'Sorry, something went wrong. Please try again.', isStreaming: false }
              : m));
            break;
          }
          try {
            const t = JSON.parse(payload);
            setMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, content: m.content + t } : m));
          } catch { /* skip */ }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setMessages(prev => prev.map((m, i) => i === prev.length - 1
        ? { ...m, content: language === 'ml' ? 'കണക്ഷൻ പ്രശ്‌നം. വീണ്ടും ശ്രമിക്കൂ.' : 'Connection error. Please try again.', isStreaming: false }
        : m));
    } finally {
      setIsStreaming(false);
    }
  }, [messages, inputText, isStreaming, hospitalId, language, stopSilenceDetection, resetTranscript]);

  useEffect(() => { handleSendRef.current = handleSend; }, [handleSend]);

  useEffect(() => { scrollRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const micBtnClass = {
    idle:      'bg-emerald-50 text-emerald-600 hover:bg-emerald-100',
    recording: 'bg-red-500 text-white ring-4 ring-red-100 animate-pulse',
  }[micState];

  const micLabel = {
    idle:      language === 'en' ? 'Tap to speak' : 'സംസാരിക്കുക',
    recording: language === 'en' ? 'Listening… tap to cancel' : 'കേൾക്കുന്നു… റദ്ദാക്കാൻ ടാപ്പ് ചെയ്യൂ',
  }[micState];

  if (!browserSupportsSpeechRecognition) {
    return (
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl overflow-hidden border border-slate-200 flex flex-col">
        <div className="bg-emerald-600 p-4 text-white shrink-0">
          <h3 className="font-bold flex items-center gap-2"><Activity className="w-4 h-4" /> Ask Arogya</h3>
        </div>
        <div className="p-6 bg-slate-50 flex-1">
          <div className="bg-white rounded-xl p-4 border border-slate-100 shadow-sm mb-4">
            <p className="text-sm text-gray-700" style={{ fontFamily: "'Noto Sans Malayalam', sans-serif" }}>
              {language === 'ml' ? "👋 നമസ്കാരം! ഞാൻ ആരോഗ്യ. ടൈപ്പ് ചെയ്ത് ചോദ്യം ചോദിക്കൂ." : "👋 Hello! I am Arogya. You can type your question below."}
            </p>
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <p className="text-xs text-amber-700 mt-1">
              {language === 'ml' ? 'ശബ്ദം ഉപയോഗിക്കാൻ Chrome ബ്രൗസർ ഉപയോഗിക്കൂ.' : 'Voice input requires Chrome browser.'}
            </p>
          </div>
        </div>
        <div className="p-4 border-t bg-white">
          <div className="flex items-center gap-2">
            <input type="text" value={inputText} onChange={e => setInputText(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend(inputText)}
              placeholder={language === 'ml' ? "ചോദിക്കൂ..." : "Ask anything..."}
              className="flex-1 bg-slate-100 border-none rounded-full px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500"
              style={{ fontFamily: "'Noto Sans Malayalam', sans-serif" }} />
            <button onClick={() => handleSend(inputText)} disabled={!inputText.trim() || isStreaming}
              className="p-2 bg-emerald-600 text-white rounded-full hover:bg-emerald-700 disabled:opacity-40">
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md bg-white rounded-2xl shadow-xl overflow-hidden border border-slate-200 flex flex-col h-[650px]">

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Malayalam:wght@400;500;700&display=swap');
        .ml-text { font-family: 'Noto Sans Malayalam', 'Manjari', sans-serif !important; }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
      `}</style>

      {/* Header */}
      <div className="bg-emerald-600 p-4 text-white shrink-0 shadow-md">
        <div className="flex justify-between items-center">
          <h3 className="font-bold flex items-center gap-2">
            <Activity className="w-4 h-4" /> Ask Arogya
          </h3>
          <button
            onClick={() => setLanguage(l => l === 'en' ? 'ml' : 'en')}
            disabled={micState === 'recording'}
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

        {micState === 'recording' && transcript && (
          <div className="flex justify-end">
            <div className="bg-emerald-50 text-emerald-800 px-4 py-2 rounded-2xl rounded-tr-none text-sm italic border border-emerald-200 shadow-sm max-w-[85%] ml-text">
              <span className="text-[10px] text-emerald-500 font-bold block mb-1 not-italic uppercase tracking-wider">
                {language === 'en' ? 'Hearing…' : 'കേൾക്കുന്നു…'}
              </span>
              {transcript}
            </div>
          </div>
        )}

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
            <button key={i} disabled={isStreaming || micState === 'recording'} onClick={() => handleSend(text)}
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
            onKeyDown={e => e.key === 'Enter' && !isStreaming && handleSend(inputText)}
            placeholder={micState === 'recording'
              ? (language === 'en' ? 'Listening…' : 'കേൾക്കുന്നു…')
              : (language === 'en' ? 'Ask anything…' : 'ചോദിക്കൂ…')}
            disabled={isStreaming || micState === 'recording'}
            className="flex-1 bg-slate-100 border-none rounded-full px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-60 ml-text"
            style={{ fontFamily: "'Noto Sans Malayalam', sans-serif" }} />
          <button onClick={() => handleSend(inputText)} disabled={isStreaming || !inputText.trim()}
            className="p-2 bg-emerald-600 text-white rounded-full hover:bg-emerald-700 disabled:opacity-40">
            <Send className="w-4 h-4" />
          </button>
        </div>

        <div className="flex flex-col items-center">
          <button type="button" onClick={toggleMic} disabled={isStreaming}
            className={`p-4 rounded-full transition-all transform active:scale-90 shadow-lg disabled:opacity-50 ${micBtnClass}`}
            aria-label={micLabel}>
            {micState === 'recording' ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
          </button>
          <p className="text-[9px] uppercase tracking-widest text-slate-400 font-black mt-2 text-center ml-text">{micLabel}</p>
        </div>

      </div>
    </div>
  );
};

export default Chat;
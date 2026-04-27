import React, { useState, useEffect, useRef, useCallback } from 'react';
import ChatMessage from './ChatMessage';
import { Mic, MicOff, Send, Zap, Activity, Loader2, AlertCircle } from 'lucide-react';

interface ChatProps { hospitalId: string; }

interface Message {
  role: 'user' | 'assistant';
  content: string;
  isWelcome?: boolean;
  isStreaming?: boolean;
}

type MicState = 'idle' | 'recording' | 'transcribing';

const FALLBACK_SUGGESTIONS = {
  en: ["What can Arogya help me with?", "Which doctors are available?", "How do I contact the hospital?", "Tell me about this hospital"],
  ml: ["ആരോഗ്യ എന്തൊക്കെ സഹായിക്കും?", "ഏത് ഡോക്ടർ ഉണ്ട്?", "ആശുപത്രിയിൽ എങ്ങനെ ബന്ധപ്പെടാം?", "ഈ ആശുപത്രിയെക്കുറിച്ച് പറയൂ"],
};

const LOADING_WELCOME = {
  en: "👋 Hello! I am **Arogya**. Loading your hospital information…",
  ml: "👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**. ആശുപത്രി വിവരങ്ങൾ ലോഡ് ചെയ്യുന്നു…",
};

function buildHistory(messages: Message[]): { role: string; content: string }[] {
  return messages.filter(m => !m.isWelcome && !m.isStreaming).map(m => ({ role: m.role, content: m.content }));
}

function getBaseURL(): string {
  return (import.meta as any).env?.VITE_API_URL
    || (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
      ? 'http://localhost:8000/api/v1'
      : 'https://hospital-ai-platform.onrender.com/api/v1');
}

const Chat: React.FC<ChatProps> = ({ hospitalId }) => {
  const [language, setLanguage] = useState<'en' | 'ml'>('ml');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [inputText, setInputText] = useState('');
  const [micState, setMicState] = useState<MicState>('idle');
  const [micError, setMicError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<{ en: string[]; ml: string[] }>(FALLBACK_SUGGESTIONS);

  const sessionToken = useRef<string>(
    sessionStorage.getItem('bookingSessionToken') || (() => {
      const t = crypto.randomUUID();
      sessionStorage.setItem('bookingSessionToken', t);
      return t;
    })()
  );
  
  const welcomeCache = useRef<{ en: string; ml: string } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Whisper Audio Refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // ── Fetch welcome ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!hospitalId) return;
    const token = localStorage.getItem('token');
    setMessages([{ role: 'assistant', content: LOADING_WELCOME[language], isWelcome: true }]);
    if (welcomeCache.current) {
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
          setMessages([{ role: 'assistant', content: language === 'ml'
            ? "👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**. എനിക്ക് എങ്ങനെ സഹായിക്കാനാകും?"
            : "👋 Hello! I am **Arogya**. How can I help you today?", isWelcome: true }]);
        }
      })
      .catch(() => {
        setMessages([{ role: 'assistant', content: language === 'ml'
          ? "👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**. എനിക്ക് എങ്ങനെ സഹായിക്കാനാകും?"
          : "👋 Hello! I am **Arogya**. How can I help you today?", isWelcome: true }]);
      });
  }, [hospitalId]);

  useEffect(() => {
    setMessages(prev => {
      if (!prev.length || !prev[0].isWelcome) return prev;
      const newContent = welcomeCache.current
        ? welcomeCache.current[language]
        : language === 'ml'
          ? "👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**. എനിക്ക് എങ്ങനെ സഹായിക്കാനാകും?"
          : "👋 Hello! I am **Arogya**. How can I help you today?";
      return [{ ...prev[0], content: newContent }, ...prev.slice(1)];
    });
  }, [language]);

  // ── Fetch suggestions ─────────────────────────────────────────────────────
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

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => () => {
    if (mediaRecorderRef.current && micState === 'recording') {
      mediaRecorderRef.current.stop();
    }
    abortRef.current?.abort();
  }, [micState]);

  // ── Whisper Mic Logic ─────────────────────────────────────────────────────
// Replace your existing toggleMic with this:
  const toggleMic = async () => {
    setMicError(null);

    if (micState === 'idle') {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;
        audioChunksRef.current = [];

        // --- NATIVE SILENCE DETECTION (Upgraded) ---
        // Some browsers suspend audio context by default, we ensure it's running
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        const audioContext = new AudioContextClass();
        if (audioContext.state === 'suspended') {
            await audioContext.resume();
        }
        
        const analyser = audioContext.createAnalyser();
        analyser.minDecibels = -70; // Catch slightly softer voices
        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);
        
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        let silenceStart = Date.now();
        let isSpeaking = false;

        const checkSilence = () => {
          if (mediaRecorder.state !== 'recording') {
            audioContext.close();
            return;
          }
          
          analyser.getByteFrequencyData(dataArray);
          // Use Math.max for PEAK volume instead of average to ignore background hums
          const maxVolume = Math.max(...dataArray);

          if (maxVolume > 25) { 
            silenceStart = Date.now();
            isSpeaking = true;
          } else {
            const timeSilent = Date.now() - silenceStart;
            // Stop recording after 2 seconds of silence (if they spoke) or 6 seconds (if they never spoke)
            if ((isSpeaking && timeSilent > 2000) || (!isSpeaking && timeSilent > 6000)) {
              mediaRecorder.stop();
              return;
            }
          }
          requestAnimationFrame(checkSilence);
        };
        checkSilence(); // Start the monitoring loop
        // --------------------------------

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            audioChunksRef.current.push(event.data);
          }
        };

        mediaRecorder.onstop = async () => {
          setMicState('transcribing');
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append('file', audioBlob, 'recording.webm');
          formData.append('language', language);

          try {
            const token = localStorage.getItem('token');
            const res = await fetch(`${getBaseURL()}/ai/transcribe`, {
              method: 'POST',
              headers: token ? { Authorization: `Bearer ${token}` } : {},
              body: formData
            });
            
            if (!res.ok) throw new Error("Transcription failed");
            const data = await res.json();
            
            // Set UI back to idle FIRST, then trigger the auto-send
            setMicState('idle');
            
            if (data.transcript && data.transcript.trim()) {
                if (handleSendRef.current) {
                    // Send the transcript directly to the pipeline
                    handleSendRef.current(data.transcript.trim());
                }
            }
          } catch (error) {
            console.error("Whisper error:", error);
            setMicError(language === 'ml' ? 'ശബ്ദം മനസ്സിലാക്കാൻ കഴിഞ്ഞില്ല.' : 'Failed to transcribe audio.');
            setMicState('idle'); // Ensure state resets on error
          } finally {
            stream.getTracks().forEach(track => track.stop());
          }
        };

        mediaRecorder.start();
        setMicState('recording');
      } catch (err) {
        setMicError(language === 'ml' 
          ? 'മൈക്രോഫോൺ ആക്സസ് തടഞ്ഞിരിക്കുന്നു. അനുവദിക്കൂ.' 
          : 'Microphone access denied. Please check settings.');
      }
    } else if (micState === 'recording') {
      mediaRecorderRef.current?.stop();
    }
  };

  // ── Send Logic ────────────────────────────────────────────────────────────
// Replace your existing handleSend with this:
  const handleSend = useCallback(async (text?: string) => {
    // If text is passed directly (from the mic), use it. Otherwise use the input box.
    const msg = (typeof text === 'string' ? text : inputText).trim();
    
    // Notice we removed the micState check here so the auto-send isn't blocked!
    if (!msg || isStreaming) return;

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setInputText('');
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
          session_token: sessionToken.current,
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
              ? { ...m, content: language === 'ml' ? 'ക്ഷമിക്കണം, പ്രശ്‌നം ഉണ്ടായി. വീണ്ടും ശ്രമിക്കൂ.' : 'Sorry, something went wrong. Please try again.', isStreaming: false }
              : m));
            break;
          }
          try {
            const t = JSON.parse(payload);
            setMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, content: m.content + t } : m));
          } catch { /* skip malformed frame */ }
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
  }, [messages, inputText, isStreaming, hospitalId, language]);

  useEffect(() => { scrollRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const micBtnClass = {
    idle:         'bg-emerald-50 text-emerald-600 hover:bg-emerald-100',
    recording:    'bg-red-500 text-white ring-4 ring-red-100 animate-pulse',
    transcribing: 'bg-emerald-600 text-white opacity-80',
  }[micState];

  const micLabel = {
    idle:         language === 'en' ? 'Tap to speak' : 'സംസാരിക്കുക',
    recording:    language === 'en' ? 'Tap to finish' : 'അവസാനിപ്പിക്കാൻ ടാപ്പ് ചെയ്യൂ',
    transcribing: language === 'en' ? 'Translating...' : 'വിവർത്തനം ചെയ്യുന്നു...',
  }[micState];
  const handleSendRef = useRef<((text: string) => Promise<void>) | null>(null);
  useEffect(() => { handleSendRef.current = handleSend; }, [handleSend]);

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
            onKeyDown={e => e.key === 'Enter' && !isStreaming && handleSend(inputText)}
            placeholder={language === 'en' ? 'Ask anything…' : 'ചോദിക്കൂ…'}
            disabled={isStreaming || micState !== 'idle'}
            className="flex-1 bg-slate-100 border-none rounded-full px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-60 ml-text"
            style={{ fontFamily: "'Noto Sans Malayalam', sans-serif" }} />
          <button onClick={() => handleSend(inputText)} disabled={isStreaming || !inputText.trim() || micState !== 'idle'}
            className="p-2 bg-emerald-600 text-white rounded-full hover:bg-emerald-700 disabled:opacity-40">
            <Send className="w-4 h-4" />
          </button>
        </div>

        <div className="flex flex-col items-center">
          <button type="button" onClick={toggleMic} disabled={isStreaming || micState === 'transcribing'}
            className={`p-4 rounded-full transition-all transform active:scale-90 shadow-lg disabled:opacity-50 flex items-center justify-center ${micBtnClass}`}
            aria-label={micLabel}>
            {micState === 'recording' ? <MicOff className="w-6 h-6" /> : 
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
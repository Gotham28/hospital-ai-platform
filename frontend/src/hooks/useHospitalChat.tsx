import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useMicVAD, utils } from "@ricky0123/vad-react";

interface Message {
  role: 'user' | 'assistant';
  content: string;
  isWelcome?: boolean;
  isStreaming?: boolean;
}

type MicState = 'idle' | 'recording' | 'transcribing';

const FALLBACK_SUGGESTIONS = {
  en: ["What can you help me with?", "Which doctors are available?", "How do I contact the hospital?", "Tell me about this hospital"],
  ml: ["നിങ്ങൾക്ക് എന്നെ എങ്ങനെ സഹായിക്കാനാകും?", "ഏത് ഡോക്ടർമാരുണ്ട്?", "ആശുപത്രിയുമായി എങ്ങനെ ബന്ധപ്പെടാം?", "ഈ ആശുപത്രിയെക്കുറിച്ച് പറയൂ"],
};

function getBaseURL(): string {
  return (import.meta as any).env?.VITE_API_URL
    || (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
      ? 'http://localhost:8000/api/v1'
      : 'https://hospital-ai-platform.onrender.com/api/v1');
}

export function useHospitalChat(hospitalId: string) {
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
  const abortRef = useRef<AbortController | null>(null);
  const handleSendRef = useRef<((text: string) => Promise<void>) | null>(null);
  const micActiveRef = useRef(false);
  const languageRef = useRef(language);
  useEffect(() => { languageRef.current = language; }, [language]);

  // --- 1. Fetch Welcome & Suggestions ---
  useEffect(() => {
    if (!hospitalId) return;
    const token = localStorage.getItem('token');
    
    // Set initial loading message
    setMessages([{ role: 'assistant', content: language === 'ml' ? "വിവരങ്ങൾ ലോഡ് ചെയ്യുന്നു..." : "Loading info...", isWelcome: true }]);

    fetch(`${getBaseURL()}/ai/welcome/${hospitalId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.en && data?.ml) {
          welcomeCache.current = { en: data.en, ml: data.ml };
          setMessages([{ role: 'assistant', content: data[language], isWelcome: true }]);
        }
      }).catch(() => {});

    fetch(`${getBaseURL()}/ai/suggestions/${hospitalId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.en && data?.ml) setSuggestions(data); })
      .catch(() => {});
  }, [hospitalId]);

  // Update welcome message if language toggles
  useEffect(() => {
    setMessages(prev => {
      if (!prev.length || !prev[0].isWelcome || !welcomeCache.current) return prev;
      return [{ ...prev[0], content: welcomeCache.current[language] }, ...prev.slice(1)];
    });
  }, [language]);

  // --- 2. The Text Chat Logic ---
  const handleSend = useCallback(async (text?: string) => {
    const msg = (typeof text === 'string' ? text : inputText).trim();
    if (!msg || isStreaming) return;

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setInputText('');
    setMicError(null);

    const historySnapshot = messages.filter(m => !m.isWelcome && !m.isStreaming).map(m => ({ role: m.role, content: m.content }));
    setMessages(prev => [...prev, { role: 'user', content: msg }, { role: 'assistant', content: '', isStreaming: true }]);
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
          try {
            const t = JSON.parse(payload);
            setMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, content: m.content + t } : m));
          } catch { /* skip */ }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setMessages(prev => prev.map((m, i) => i === prev.length - 1
        ? { ...m, content: language === 'ml' ? 'കണക്ഷൻ പ്രശ്‌നം. വീണ്ടും ശ്രമിക്കൂ.' : 'Connection error.', isStreaming: false }
        : m));
    } finally {
      setIsStreaming(false);
    }
  }, [messages, inputText, isStreaming, hospitalId, language]);

  useEffect(() => { handleSendRef.current = handleSend; }, [handleSend]);

  // --- 3. The Silero VAD Mic Logic ---
// --- 3. The Silero VAD Mic Logic ---
const vadOptions = useMemo(() => ({
  startOnLoad: false,
  baseAssetPath: "/vad-assets/",
  onnxWASMBasePath: "/vad-assets/",
  model: "legacy" as const,
  positiveSpeechThreshold: 0.6,
  negativeSpeechThreshold: 0.35,
  minSpeechMs: 250,
  redemptionMs: 1500,
  onSpeechStart: () => {
    if (micActiveRef.current) setMicState('recording');
  },
  onSpeechEnd: async (audio) => {
    if (!micActiveRef.current) return;
  
  micActiveRef.current = false;  // ← ADD: lock it immediately
  vadPause();                     // ← ADD: stop VAD right away
  setMicState('transcribing');
  
    try {
      const wavBuffer = utils.encodeWAV(audio);
      const audioBlob = new Blob([wavBuffer], { type: 'audio/wav' });
      const formData = new FormData();
      formData.append('file', audioBlob, 'recording.wav');
      formData.append('language', language);
      formData.append('hospital_id', String(parseInt(hospitalId) || 0));
      const token = localStorage.getItem('token');
      const res = await fetch(`${getBaseURL()}/ai/transcribe`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData
      });
      if (!res.ok) throw new Error("Transcription failed");
      const data = await res.json();
      setMicState('idle');
      if (data.transcript?.trim() && handleSendRef.current) {
        handleSendRef.current(data.transcript.trim());
      }
    } catch (error) {
      setMicError(language === 'ml' ? 'ശബ്ദം മനസ്സിലാക്കാൻ കഴിഞ്ഞില്ല.' : 'Failed to transcribe audio.');
      setMicState('idle');
    }
  },
  onVADMisfire: () => {
    if (!micActiveRef.current) return;
    setMicState('idle');
  }
}), []); // empty — refs and setters are stable, language captured via ref below

const { loading: vadLoading, errored: vadErrored, start: vadStart, pause: vadPause } = useMicVAD(vadOptions);

const toggleMic = () => {
  setMicError(null);
  if (micState === 'recording' || micState === 'transcribing') {
    micActiveRef.current = false;
    vadPause();           // ✅ top-level, not vad.pause()
    setMicState('idle');
  } else {
    if (vadLoading) {
      setMicError(language === 'en' ? 'Voice AI is still loading...' : 'ശബ്ദ AI ലോഡുചെയ്യുന്നു...');
      return;
    }
    if (vadErrored) {
      setMicError(language === 'en' ? 'Voice AI failed to load.' : 'ശബ്ദ AI പരാജയപ്പെട്ടു.');
      return;
    }
    micActiveRef.current = true;
    vadStart();           // ✅ top-level, not vad.start()
    setMicState('recording');
  }
};

// Update the return value — remove `vad`, expose vadLoading instead
return {
  language, setLanguage, messages, isStreaming,
  inputText, setInputText, micState, micError,
  suggestions, handleSend, toggleMic,
  vadLoading  // ✅ replaces `vad` in the return
};}
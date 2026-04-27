import { useState, useEffect, useRef, useCallback } from 'react';
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
  const vad = useMicVAD({
  startOnLoad: false,
  // Point BOTH paths to the same CDN dist folder for vad-web@0.0.30
  baseAssetPath: "https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.30/dist/",
  onnxWASMBasePath: "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.18.0/dist/",
  model: "legacy", // "legacy" = silero_vad_legacy.onnx (the v4 model, what you were using before)
  onSpeechStart: () => setMicState('recording'),
  onSpeechEnd: async (audio) => {
      vad.pause(); 
      setMicState('transcribing');

      try {
        const wavBuffer = utils.encodeWAV(audio);
        const audioBlob = new Blob([wavBuffer], { type: 'audio/wav' });
        
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.wav');
        formData.append('language', language);
        formData.append('hospital_id', hospitalId); 

        const token = localStorage.getItem('token');
        const res = await fetch(`${getBaseURL()}/ai/transcribe`, {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData
        });
        
        if (!res.ok) throw new Error("Transcription failed");
        const data = await res.json();
        
        setMicState('idle');
        if (data.transcript && data.transcript.trim() && handleSendRef.current) {
            handleSendRef.current(data.transcript.trim());
        }
      } catch (error) {
        setMicError(language === 'ml' ? 'ശബ്ദം മനസ്സിലാക്കാൻ കഴിഞ്ഞില്ല.' : 'Failed to transcribe audio.');
        setMicState('idle'); 
      }
    },
    onVADMisfire: () => {
      setMicState('idle');
      vad.pause();
    }
  });

const toggleMic = () => {
    setMicError(null);

    // FORCE OFF: If our UI says it's recording, trust the UI and force it to pause, 
    // regardless of what the VAD engine thinks it's doing.
    if (micState === 'recording' || micState === 'transcribing') {
      vad.pause();
      setMicState('idle');
    } else {
      // PREVENT START: Don't let the user click if the neural network is still downloading
      if (vad.loading) {
        setMicError(language === 'en' ? 'Voice AI is still loading...' : 'ശബ്ദ AI ലോഡുചെയ്യുന്നു...');
        return;
      }
      if (vad.errored) {
        setMicError(language === 'en' ? 'Voice AI failed to load.' : 'ശബ്ദ AI പരാജയപ്പെട്ടു.');
        return;
      }

      vad.start();
      setMicState('recording'); 
    }
  };

  return {
    language,
    setLanguage,
    messages,
    isStreaming,
    inputText,
    setInputText,
    micState,
    micError,
    suggestions,
    handleSend,
    toggleMic,vad
  };
} 
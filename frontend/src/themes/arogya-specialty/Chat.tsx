import React, { useState, useEffect, useRef, useCallback } from 'react';
import SpeechRecognition, { useSpeechRecognition } from 'react-speech-recognition';
import ChatMessage from './ChatMessage';
import { Mic, MicOff, Loader2, Activity, Send, Zap } from 'lucide-react';

interface ChatProps { hospitalId: string; }

interface Message {
  role: 'user' | 'assistant';
  content: string;
  isWelcome?: boolean;
  // isStreaming flags the message currently being written by the AI.
  // ChatMessage renders a blinking cursor when this is true.
  isStreaming?: boolean;
}

const SUGGESTIONS = {
  'en-US': ["Who is the cardiologist today?", "Where is the pharmacy?", "Visiting hours?", "Emergency contact"],
  'ml-IN': ["കാർഡിയോളജിസ്റ്റ് ആരാണ്?", "ഫാർമസി എവിടെയാണ്?", "സന്ദർശന സമയം?", "അടിയന്തര നമ്പർ"]
};

function buildHistory(messages: Message[]): { role: string; content: string }[] {
  return messages
    .filter(m => !m.isWelcome && !m.isStreaming)
    .map(m => ({ role: m.role, content: m.content }));
}

// Resolve the API base URL the same way axios.ts does, but for raw fetch.
// We cannot use the axios instance for streaming because axios buffers
// the entire response before resolving — that defeats the whole point.
function getBaseURL(): string {
  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000/api/v1'
    : 'https://hospital-ai-platform.onrender.com/api/v1';
}

const Chat: React.FC<ChatProps> = ({ hospitalId }) => {
  const [language, setLanguage] = useState<'en-US' | 'ml-IN'>('ml-IN');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [inputText, setInputText] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  // abortRef lets us cancel an in-flight stream if the user sends another
  // message before the current one finishes.
  const abortRef = useRef<AbortController | null>(null);

  const { transcript, listening, resetTranscript, browserSupportsSpeechRecognition } = useSpeechRecognition();

  const handleSend = useCallback(async (text: string) => {
    const messageToSend = (text || inputText || transcript).trim();
    if (!messageToSend || isStreaming) return;

    // Cancel any in-flight stream before starting a new one
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    SpeechRecognition.stopListening();
    setInputText('');
    resetTranscript();

    // Snapshot history BEFORE adding the new user message to state.
    // React state updates are async — messages won't include the new turn yet.
    const historySnapshot = buildHistory(messages);

    // Add user message immediately so the UI feels instant
    setMessages(prev => [...prev, { role: 'user', content: messageToSend }]);

    // Add a placeholder assistant message marked isStreaming=true.
    // We'll update its content token-by-token as chunks arrive.
    setMessages(prev => [...prev, { role: 'assistant', content: '', isStreaming: true }]);
    setIsStreaming(true);

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${getBaseURL()}/ai/chat-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // Attach JWT the same way the axios interceptor does
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          question: messageToSend,
          hospital_id: parseInt(hospitalId),
          language: language === 'ml-IN' ? 'ml' : 'en',
          history: historySnapshot,
        }),
        signal: abortRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Decode the chunk and append to the buffer.
        // Chunks are not guaranteed to be aligned to SSE frame boundaries —
        // a single read() call can contain multiple frames or a partial one.
        buffer += decoder.decode(value, { stream: true });

        // Split on the SSE double-newline frame separator
        const frames = buffer.split('\n\n');
        // Keep the last (potentially incomplete) frame in the buffer
        buffer = frames.pop() ?? '';

        for (const frame of frames) {
          if (!frame.startsWith('data: ')) continue;
          const payload = frame.slice(6); // strip "data: "

          if (payload === '[DONE]') {
            // Stream finished — clear the isStreaming flag on the last message
            setMessages(prev =>
              prev.map((m, i) =>
                i === prev.length - 1 ? { ...m, isStreaming: false } : m
              )
            );
            break;
          }

          if (payload.startsWith('[ERROR]')) {
            const errText = payload.slice(8);
            setMessages(prev =>
              prev.map((m, i) =>
                i === prev.length - 1
                  ? { ...m, content: `Sorry, something went wrong. Please try again.`, isStreaming: false }
                  : m
              )
            );
            console.error('Stream error from backend:', errText);
            break;
          }

          // Regular token — JSON-encoded by the backend to handle
          // special characters and Unicode (Malayalam) safely
          try {
            const tokenText = JSON.parse(payload);
            setMessages(prev =>
              prev.map((m, i) =>
                i === prev.length - 1
                  ? { ...m, content: m.content + tokenText }
                  : m
              )
            );
          } catch {
            // Malformed JSON in a single token — skip it silently
          }
        }
      }
    } catch (err: unknown) {
      // AbortError is expected when we cancel a previous stream — not a real error
      if (err instanceof Error && err.name === 'AbortError') return;

      setMessages(prev =>
        prev.map((m, i) =>
          i === prev.length - 1
            ? { ...m, content: 'Error connecting to Arogya. Please try again.', isStreaming: false }
            : m
        )
      );
    } finally {
      setIsStreaming(false);
    }
  }, [messages, inputText, transcript, isStreaming, hospitalId, language]);

  const toggleMic = () => {
    if (listening) {
      SpeechRecognition.stopListening();
    } else {
      resetTranscript();
      SpeechRecognition.startListening({ continuous: true, language });
    }
  };

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    if (transcript && listening) {
      timer = setTimeout(() => handleSend(transcript), 2500);
    }
    return () => clearTimeout(timer);
  }, [transcript, listening]);

  useEffect(() => {
    const welcome = language === 'ml-IN'
      ? "👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**. എനിക്ക് എങ്ങനെ സഹായിക്കാനാകും?"
      : "👋 Hello! I am **Arogya**. How can I help you today?";
    setMessages([{ role: 'assistant', content: welcome, isWelcome: true }]);
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

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((msg, idx) => (
          <ChatMessage
            key={idx}
            role={msg.role}
            content={msg.content}
            isStreaming={msg.isStreaming}
          />
        ))}

        {listening && transcript && (
          <div className="flex justify-end">
            <div className="bg-emerald-50 text-emerald-700 px-4 py-2 rounded-2xl rounded-tr-none text-sm italic border border-emerald-100 shadow-sm animate-pulse">
              {transcript}...
            </div>
          </div>
        )}

        {/* Show a subtle indicator only during the very first moment before
            any tokens arrive — once content starts flowing, isStreaming on
            the message itself drives the cursor in ChatMessage */}
        {isStreaming && messages[messages.length - 1]?.content === '' && (
          <div className="flex items-center gap-2 text-emerald-600 p-2 bg-white rounded-lg w-fit shadow-sm border border-slate-100">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-[10px] font-bold">Arogya is thinking...</span>
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
              disabled={isStreaming}
              onClick={() => handleSend(text)}
              className="flex-none bg-white border border-emerald-100 text-emerald-700 text-[11px] px-3 py-1.5 rounded-full shadow-sm hover:bg-emerald-50 active:scale-95 transition-all disabled:opacity-40"
            >
              <Zap className="w-3 h-3 text-amber-400 fill-amber-400 inline mr-1" />{text}
            </button>
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="p-4 border-t bg-white shrink-0">
        <div className="flex items-center gap-2 mb-4">
          <input
            type="text"
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !isStreaming && handleSend(inputText)}
            placeholder={language === 'en-US' ? "Ask anything..." : "ചോദിക്കൂ..."}
            disabled={isStreaming}
            className="flex-1 bg-slate-100 border-none rounded-full px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-60"
          />
          <button
            onClick={() => handleSend(inputText)}
            disabled={isStreaming}
            className="p-2 bg-emerald-600 text-white rounded-full hover:bg-emerald-700 transition-colors shadow-sm disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        <div className="flex flex-col items-center">
          <button
            type="button"
            onClick={toggleMic}
            disabled={isStreaming}
            className={`p-4 rounded-full transition-all transform active:scale-90 shadow-lg disabled:opacity-50 ${
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
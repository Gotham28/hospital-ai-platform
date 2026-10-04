/**
 * iris-hospitals/Chat.tsx
 * ─────────────────────────────────────────────────────────────────
 * IRIS THEME — full chat widget UI, LIGHT rebuild (voice + text +
 * suggestions), against the approved Claude Design frames
 * 01/02/03/04/05/06/08.
 *
 * ALL data logic comes from useChatCore(). Zero API calls here.
 * Presentation only.
 *
 * Design frame 07 (translation-unavailable notice) is deliberately
 * NOT built here — detecting the [TRANSLATION_UNAVAILABLE] sentinel
 * requires a change to the shared useHospitalChat hook, out of
 * scope for this task. See docs/STATUS.md / .agents/REPORT.md for
 * the reachability evidence and the deferral.
 *
 * A few design elements assume data useChatCore does not expose
 * (a live partial transcript during voice-to-text, elapsed
 * recording time). Handled per-element below with a comment at the
 * point of divergence — full list in the task's close-out report.
 * ─────────────────────────────────────────────────────────────────
 */

import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, Send, Loader2, AlertCircle } from 'lucide-react';
import ChatMessage from './ChatMessage';
import { useChatCore } from '../../components/common/ChatCore';
import irisLogo from './iris-logo.png';
import { fadeUp, stagger } from './motion';

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
    vadLoading,
  } = useChatCore(hospitalId) as ChatCoreReturn;

  const isMalayalam = language === 'ml';
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── "Switched to <language>" transient notice — frame 06 ──────
  // Local, ephemeral UI state only; not sourced from the hook, not
  // persisted, not a data-flow change.
  const [showSwitchNotice, setShowSwitchNotice] = useState(false);
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    setShowSwitchNotice(true);
    const t = setTimeout(() => setShowSwitchNotice(false), 3000);
    return () => clearTimeout(t);
  }, [language]);

  // ── Recording elapsed time — frame 05 ──────────────────────────
  // useChatCore exposes no elapsed-time field; this is a local,
  // presentation-only timer, not a hook or data-flow change.
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  useEffect(() => {
    if (micState !== 'recording') {
      setRecordingSeconds(0);
      return;
    }
    const interval = setInterval(() => setRecordingSeconds(s => s + 1), 1000);
    return () => clearInterval(interval);
  }, [micState]);
  const recordingTimeLabel = `${Math.floor(recordingSeconds / 60)}:${String(recordingSeconds % 60).padStart(2, '0')}`;

  const micHint: Record<MicState, string> = {
    idle:         vadLoading
                    ? (isMalayalam ? 'ലോഡുചെയ്യുന്നു…' : 'Loading…')
                    : (isMalayalam ? 'സംസാരിക്കാൻ മൈക്ക് അമർത്തൂ' : 'Tap the mic to speak'),
    recording:    isMalayalam ? 'കേൾക്കുന്നു. പൂർത്തിയായാൽ നിർത്തൂ അമർത്തൂ.' : 'Listening. Tap stop when finished.',
    transcribing: isMalayalam ? 'പറഞ്ഞത് എഴുതി മാറ്റുന്നു' : 'Transcribing what you said',
  };

  const showChips = messages.length <= 1;

  return (
    <div className="w-full max-w-[375px] md:max-w-[440px] bg-iris-surface-raised border border-iris-border rounded-iris overflow-hidden flex flex-col">
      <style>{`
        .iris-scrollbar::-webkit-scrollbar { width: 4px; }
        .iris-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .iris-scrollbar::-webkit-scrollbar-thumb { background: var(--color-iris-sage); border-radius: 2px; }
        @keyframes irisBlink { 0%, 100% { opacity: 1 } 50% { opacity: 0 } }
        @keyframes irisDot {
          0%, 100% { opacity: 0.3; transform: scale(0.85); }
          50% { opacity: 1; transform: scale(1); }
        }
        @keyframes irisSweep { 0% { transform: translateX(-100%) } 100% { transform: translateX(320%) } }
        @keyframes irisRipple {
          0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--color-iris-danger) 34%, transparent) }
          100% { box-shadow: 0 0 0 16px color-mix(in srgb, var(--color-iris-danger) 0%, transparent) }
        }
        @media (prefers-reduced-motion: reduce) {
          .iris-dot { animation: none !important; opacity: 1; transform: none; }
          .iris-sweep { animation: none !important; width: 40%; }
          .iris-ripple { animation: none !important; box-shadow: none; }
        }
      `}</style>

      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-[12px] md:gap-[16px] p-[16px] md:px-[24px] bg-iris-surface-raised border-b border-iris-border">
        <img src={irisLogo} alt="IRIS" width={256} height={75} className="h-[28px] w-auto block" />
        <div className="flex items-center gap-[4px] p-[4px] bg-iris-accent-surface rounded-iris-sm">
          <button
            onClick={() => setLanguage('ml')}
            disabled={micState !== 'idle'}
            aria-pressed={isMalayalam}
            className={`px-[12px] py-[8px] rounded-iris-sm font-malayalam text-iris-label font-semibold disabled:opacity-50 transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-iris-primary touch-manipulation ${
              isMalayalam ? 'bg-iris-primary text-white' : 'text-iris-primary hover:bg-iris-mint'
            }`}
          >
            മലയാളം
          </button>
          <button
            onClick={() => setLanguage('en')}
            disabled={micState !== 'idle'}
            aria-pressed={!isMalayalam}
            className={`px-[12px] py-[8px] rounded-iris-sm text-iris-label font-semibold disabled:opacity-50 transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-iris-primary touch-manipulation ${
              !isMalayalam ? 'bg-iris-primary text-white' : 'text-iris-primary hover:bg-iris-mint'
            }`}
          >
            English
          </button>
        </div>
      </div>

      {/* ── Messages ─────────────────────────────────────────────── */}
      <div
        className="overflow-y-auto p-[24px] md:p-[32px] flex flex-col gap-[32px] iris-scrollbar"
        style={{ minHeight: '320px', height: '400px' }}
      >
        <AnimatePresence>
          {showSwitchNotice && (
            <div className="flex justify-center -mt-[8px] mb-[-24px]">
              <motion.div
                variants={fadeUp}
                initial="hidden"
                animate="show"
                exit="hidden"
                className="px-[12px] py-[8px] rounded-iris bg-iris-accent-surface text-iris-label text-iris-primary text-center"
              >
                {isMalayalam
                  ? 'മലയാളത്തിലേക്ക് മാറി. മുൻ സന്ദേശങ്ങൾ ഇംഗ്ലീഷിൽ തുടരും.'
                  : 'Switched to English. Earlier messages stay in Malayalam.'}
              </motion.div>
            </div>
          )}
        </AnimatePresence>

        {messages.map((msg, idx) => {
          // The last message starts as an empty placeholder while streaming
          // begins — skip rendering it as its own bubble here, since the
          // "thinking" indicator below covers that exact same state. Once
          // real content arrives, content !== '' and this renders normally.
          const isPendingPlaceholder = idx === messages.length - 1 && isStreaming && msg.content === '';
          if (isPendingPlaceholder) return null;
          return (
          <ChatMessage
            key={idx}
            role={msg.role}
            content={msg.content}
            isStreaming={msg.isStreaming}
            language={language}
          />
          );
        })}

        {showChips && suggestions[language]?.length > 0 && (
          <motion.div
            variants={stagger(0.05)}
            initial="hidden"
            animate="show"
            className="flex flex-wrap gap-[12px]"
          >
            {suggestions[language].map((text, i) => (
              <motion.button
                key={i}
                variants={fadeUp}
                disabled={isStreaming || micState !== 'idle'}
                onClick={() => handleSend(text)}
                className={`px-[16px] py-[12px] bg-iris-accent-surface text-iris-primary border border-iris-mint rounded-full disabled:opacity-40 transition-[background-color,scale] duration-150 active:scale-[0.98] hover:bg-iris-mint focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-iris-primary touch-manipulation ${
                  isMalayalam ? 'font-malayalam text-iris-ui-ml' : 'text-iris-ui'
                }`}
              >
                {text}
              </motion.button>
            ))}
          </motion.div>
        )}

        {isStreaming && messages[messages.length - 1]?.content === '' && (
          <div className="flex flex-col items-start gap-[8px]">
            <div className="text-iris-label uppercase tracking-[0.04em] font-semibold text-iris-text-muted">
              {isMalayalam ? 'IRIS സഹായി' : 'IRIS assistant'}
            </div>
            <div className="flex items-center gap-[12px] bg-iris-accent-surface rounded-iris px-[16px] py-[12px]">
              <div className="flex items-center gap-[4px] h-[16px]">
                <span className="iris-dot w-[8px] h-[8px] rounded-[4px] bg-iris-primary" style={{ animation: 'irisDot 1.4s ease-in-out infinite', animationDelay: '0s' }} />
                <span className="iris-dot w-[8px] h-[8px] rounded-[4px] bg-iris-primary" style={{ animation: 'irisDot 1.4s ease-in-out infinite', animationDelay: '0.2s' }} />
                <span className="iris-dot w-[8px] h-[8px] rounded-[4px] bg-iris-primary" style={{ animation: 'irisDot 1.4s ease-in-out infinite', animationDelay: '0.4s' }} />
              </div>
              <span className={`${isMalayalam ? 'font-malayalam text-iris-ui-ml' : 'text-iris-ui'} text-iris-text-muted`}>
                {isMalayalam ? 'സഹായി ചിന്തിക്കുന്നു' : 'IRIS is thinking'}
              </span>
            </div>
          </div>
        )}

        <div ref={scrollRef} />
      </div>

      {/* ── Composer ─────────────────────────────────────────────── */}
      <div className="p-[16px] md:px-[24px] bg-iris-surface-raised border-t border-iris-border">
        {micError && (
          <div role="alert" className="flex items-start gap-[8px] rounded-iris px-[12px] py-[8px] mb-[12px] bg-iris-surface border border-iris-border">
            <AlertCircle className="w-4 h-4 text-iris-danger shrink-0 mt-0.5" />
            <p className={`${isMalayalam ? 'font-malayalam text-iris-ui-ml' : 'text-iris-ui'} text-iris-danger`}>{micError}</p>
          </div>
        )}

        {micState === 'idle' && (
          <div className="flex flex-col gap-[8px]">
            <div className="flex items-end gap-[12px]">
              <button
                type="button"
                onClick={toggleMic}
                disabled={vadLoading}
                aria-label={micHint.idle}
                className="w-[44px] h-[44px] flex-none rounded-iris bg-transparent border border-iris-border-strong flex flex-col items-center justify-center gap-[2px] disabled:opacity-50 hover:bg-iris-accent-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-iris-primary touch-manipulation"
              >
                {vadLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin text-iris-primary" />
                ) : (
                  <Mic className="w-5 h-5 text-iris-primary" />
                )}
              </button>
              <input
                type="text"
                name="message"
                autoComplete="off"
                aria-label={isMalayalam ? 'ചോദ്യം ചോദിക്കൂ' : 'Ask a question'}
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !isStreaming && handleSend()}
                placeholder={isMalayalam ? 'ചോദ്യം ചോദിക്കൂ' : 'Ask a question'}
                disabled={isStreaming}
                className={`flex-1 min-w-0 p-[12px] rounded-iris-sm bg-iris-surface border border-iris-border-strong outline-none focus-visible:outline-2 focus-visible:outline-iris-primary focus-visible:outline-offset-2 focus-visible:border-iris-primary disabled:opacity-60 text-iris-text-primary placeholder:text-iris-text-muted ${
                  isMalayalam ? 'font-malayalam text-iris-ui-ml' : 'text-iris-body'
                }`}
              />
              <button
                onClick={() => handleSend()}
                disabled={isStreaming || !inputText.trim()}
                aria-label={isMalayalam ? 'അയയ്ക്കൂ' : 'Send'}
                className="w-[44px] h-[44px] flex-none rounded-iris bg-iris-primary hover:bg-iris-primary-hover disabled:bg-iris-border disabled:opacity-100 flex items-center justify-center transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-iris-primary touch-manipulation"
              >
                <Send className={`w-4 h-4 ${isStreaming || !inputText.trim() ? 'text-iris-text-muted' : 'text-white'}`} />
              </button>
            </div>
            <div className={`${isMalayalam ? 'font-malayalam text-iris-ui-ml' : 'text-iris-ui'} text-iris-text-muted`}>
              {micHint.idle}
            </div>
          </div>
        )}

        {micState === 'recording' && (
          <div
            className="flex flex-col gap-[12px] -m-[16px] md:-mx-[24px] md:-my-[16px] p-[16px] rounded-iris"
            style={{ border: '1px solid color-mix(in srgb, var(--color-iris-danger) 33%, white)' }}
          >
            <div className="flex items-center gap-[12px]">
              <button
                type="button"
                onClick={toggleMic}
                aria-label={isMalayalam ? 'നിർത്തൂ' : 'Stop'}
                className="iris-ripple w-[44px] h-[44px] flex-none rounded-iris bg-iris-danger flex items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-iris-primary touch-manipulation"
                style={{ animation: 'irisRipple 1.8s ease-out infinite' }}
              >
                <MicOff className="w-5 h-5 text-white" />
              </button>
              <div className="flex-1 min-w-0 flex items-center gap-[12px]">
                <span className="font-mono text-iris-label text-iris-text-muted">{recordingTimeLabel}</span>
              </div>
              <button
                type="button"
                onClick={toggleMic}
                className={`px-[16px] py-[12px] flex-none rounded-iris bg-iris-danger text-white font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-iris-primary touch-manipulation ${
                  isMalayalam ? 'font-malayalam text-iris-ui-ml' : 'text-iris-ui'
                }`}
              >
                {isMalayalam ? 'നിർത്തൂ' : 'Stop'}
              </button>
            </div>
            <div className={`${isMalayalam ? 'font-malayalam text-iris-ui-ml' : 'text-iris-ui'} text-iris-text-primary`}>
              {micHint.recording}
            </div>
          </div>
        )}

        {micState === 'transcribing' && (
          <div className="flex flex-col gap-[12px]">
            <div className="flex items-center gap-[12px]">
              <div className="w-[44px] h-[44px] flex-none rounded-iris bg-iris-surface border border-iris-border flex items-center justify-center opacity-45">
                <Mic className="w-5 h-5 text-iris-primary" />
              </div>
              <div className="flex-1 min-w-0 flex flex-col gap-[8px]">
                <div className={`${isMalayalam ? 'font-malayalam text-iris-ui-ml' : 'text-iris-ui'} text-iris-text-muted`}>
                  {micHint.transcribing}
                </div>
                <div className="h-[4px] rounded-[2px] overflow-hidden bg-iris-mint">
                  <div className="iris-sweep w-[30%] h-[4px] rounded-[2px] bg-iris-primary" style={{ animation: 'irisSweep 1.4s ease-in-out infinite' }} />
                </div>
              </div>
            </div>
            {/*
              Design frame 05 shows a live partial transcript in a dashed
              box here. useChatCore exposes no partial-transcript field —
              only the final `inputText` once transcription completes —
              so there is no real data to show mid-transcription. Omitted
              rather than fabricated; see close-out report.
            */}
          </div>
        )}
      </div>
    </div>
  );
};

export default Chat;

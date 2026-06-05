/**
 * iris-hospitals/AnimatedIntro.tsx
 * Fixed: logo uses /logonewiris.png (already in public/) instead of
 * the broken file:// path. Falls back gracefully if missing.
 */

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// ✅ logonewiris.png is already in frontend/public/ — just reference it directly
const LOGO_URL = '/logonewiris.png';

const demoConversation = [
  { isUser: true,  message: 'ഡോ. സുരേന്ദ്രൻ ഇന്ന് ലഭ്യമാണോ?' },
  { isUser: false, message: 'അതെ! ഡോ. സുരേന്ദ്രൻ ഇന്ന് രാവിലെ 9 മുതൽ ഉച്ചവരെ ലഭ്യമാണ് 😊' },
  { isUser: true,  message: 'അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യാമോ?' },
  { isUser: false, message: 'തീർച്ചയായും! നിങ്ങളുടെ പേരും ഇഷ്ടപ്പെട്ട സമയവും പറഞ്ഞാൽ മതി 🗓️' },
  { isUser: true,  message: 'OPD സമയം എന്താണ്?' },
  { isUser: false, message: 'OPD തിങ്കൾ മുതൽ ശനി വരെ, രാവിലെ 8 മുതൽ സന്ധ്യ 6 വരെ. എമർജൻസി 24/7 🏥' },
];

interface DemoMessage { isUser: boolean; message: string }

interface AnimatedIntroProps {
  onComplete: () => void;
  hospitalName?: string;
}

const DemoMsg: React.FC<{ msg: DemoMessage }> = ({ msg }) => (
  <motion.div
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    className={`flex ${msg.isUser ? 'justify-end' : 'justify-start'}`}
  >
    <div
      className="max-w-[80%] px-4 py-2 rounded-2xl text-sm"
      style={{
        fontFamily: "'Noto Sans Malayalam', sans-serif",
        background: msg.isUser ? '#1E40AF' : 'white',
        color: msg.isUser ? 'white' : '#1e293b',
        borderTopRightRadius: msg.isUser ? '4px' : undefined,
        borderTopLeftRadius: !msg.isUser ? '4px' : undefined,
      }}
    >
      {msg.message}
    </div>
  </motion.div>
);

const TypingDots: React.FC = () => (
  <div className="flex justify-start">
    <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-2 h-2 rounded-full bg-blue-400"
          style={{ animation: `bounce 1.2s ${i * 0.2}s infinite` }}
        />
      ))}
    </div>
    <style>{`@keyframes bounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-6px)} }`}</style>
  </div>
);

const AnimatedIntro: React.FC<AnimatedIntroProps> = ({ onComplete, hospitalName }) => {
  const [phase, setPhase] = useState<'logo' | 'text' | 'chat' | 'transition'>('logo');
  const [visibleMessages, setVisibleMessages] = useState<DemoMessage[]>([]);
  const [showTyping, setShowTyping] = useState(false);
  const [showCTA, setShowCTA] = useState(false);
  const [logoError, setLogoError] = useState(false);
  const chatRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t1 = setTimeout(() => setPhase('text'), 1800);
    const t2 = setTimeout(() => setPhase('chat'), 3500);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  useEffect(() => {
    if (phase !== 'chat') return;
    let idx = 0;
    const next = () => {
      if (idx >= demoConversation.length) {
        setTimeout(() => setShowCTA(true), 300);
        setTimeout(() => setPhase('transition'), 2000);
        return;
      }
      const msg = demoConversation[idx];
      if (!msg.isUser) {
        setShowTyping(true);
        setTimeout(() => {
          setShowTyping(false);
          setVisibleMessages(p => [...p, msg]);
          idx++;
          setTimeout(next, 500);
        }, 800);
      } else {
        setVisibleMessages(p => [...p, msg]);
        idx++;
        setTimeout(next, 400);
      }
    };
    const t = setTimeout(next, 500);
    return () => clearTimeout(t);
  }, [phase]);

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [visibleMessages, showTyping]);

  useEffect(() => {
    if (phase === 'transition') setTimeout(onComplete, 1500);
  }, [phase, onComplete]);

  return (
    <motion.div
      className="fixed inset-0 flex flex-col items-center justify-center overflow-hidden z-50"
      style={{ background: 'linear-gradient(to bottom, #0f172a, #1E40AF)' }}
      animate={phase === 'transition' ? { scale: 1.1, opacity: 0 } : { scale: 1, opacity: 1 }}
      transition={{ duration: 1, ease: 'easeInOut' }}
    >
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Malayalam:wght@400;600&display=swap');`}</style>

      {/* Logo section */}
      <motion.div
        className="flex flex-col items-center"
        animate={
          phase === 'chat' || phase === 'transition'
            ? { scale: 0.5, y: -180, opacity: phase === 'transition' ? 0 : 1 }
            : { scale: 1, y: 0, opacity: 1 }
        }
        transition={{ duration: 0.8, type: 'spring', stiffness: 100 }}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1.2, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="relative"
        >
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.15 }}
            transition={{ duration: 1.5, delay: 0.5 }}
            className="absolute inset-0 bg-white rounded-3xl blur-2xl -z-10"
            style={{ transform: 'scale(1.2)' }}
          />
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1, delay: 0.3 }}
            className="bg-white rounded-xl p-6 shadow-[0_4px_40px_rgba(255,255,255,0.1)]"
          >
            {logoError ? (
              /* Styled fallback — shown only if image truly fails to load */
              <div style={{
                fontSize: '2.5rem', fontWeight: 900, color: '#1E40AF',
                letterSpacing: '0.2em', padding: '0.5rem 1.5rem',
                fontFamily: 'sans-serif'
              }}>
                IRIS
              </div>
            ) : (
              <img
                src={LOGO_URL}
                alt={hospitalName || 'IRIS Hospitals'}
                width={300}
                height={108}
                className="object-contain"
                onError={() => setLogoError(true)}
              />
            )}
          </motion.div>
        </motion.div>

        <AnimatePresence>
          {(phase === 'text' || phase === 'chat' || phase === 'transition') && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.8 }}
              className="mt-6 text-center"
            >
              <p
                className="text-sm md:text-base tracking-wide"
                style={{ color: '#93c5fd', fontFamily: "'Noto Sans Malayalam', sans-serif" }}
              >
                കരുതലോടെ. ബുദ്ധിമാനായ AI-യോടൊപ്പം.
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Chat demo section */}
      <AnimatePresence>
        {(phase === 'chat' || phase === 'transition') && (
          <motion.div
            initial={{ y: 300, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ scale: 1.5, opacity: 0 }}
            transition={{ duration: 0.8, type: 'spring', stiffness: 100 }}
            className="absolute bottom-0 left-0 right-0 h-[65vh] flex flex-col items-center px-4"
          >
            <div className="relative w-full max-w-sm bg-[#0f172a] rounded-t-[2.5rem] border-4 border-gray-700 shadow-2xl overflow-hidden h-full">
              <div className="absolute top-2 left-1/2 -translate-x-1/2 w-24 h-5 bg-black rounded-full z-10" />

              <div className="bg-[#1E40AF] px-4 py-4 pt-8 flex items-center gap-3">
                {!logoError ? (
                  <div className="bg-white rounded-lg p-1">
                    <img
                      src={LOGO_URL}
                      alt="IRIS"
                      width={80}
                      height={28}
                      className="object-contain"
                      onError={() => setLogoError(true)}
                    />
                  </div>
                ) : (
                  <div className="bg-white rounded-lg px-2 py-1 font-bold text-blue-800 text-sm">IRIS</div>
                )}
                <span className="text-white font-semibold">IRIS AI</span>
              </div>

              <div
                ref={chatRef}
                className="bg-[#EFF6FF] h-[calc(100%-8rem)] overflow-y-auto p-4 space-y-3 scroll-smooth"
              >
                {visibleMessages.map((msg, i) => <DemoMsg key={i} msg={msg} />)}
                {showTyping && <TypingDots />}
              </div>

              <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-3 flex items-center gap-2">
                <div
                  className="flex-1 bg-gray-100 rounded-full px-4 py-2 text-sm text-gray-400"
                  style={{ fontFamily: "'Noto Sans Malayalam', sans-serif" }}
                >
                  സന്ദേശം ടൈപ്പ് ചെയ്യുക...
                </div>
                <div className="w-10 h-10 bg-[#1E40AF] rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </div>
              </div>

              <AnimatePresence>
                {showCTA && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 backdrop-blur-sm flex items-center justify-center"
                    style={{ background: 'rgba(30,64,175,0.8)' }}
                  >
                    <motion.p
                      initial={{ scale: 0.8, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ type: 'spring', stiffness: 300 }}
                      className="text-white text-xl md:text-2xl font-bold text-center px-6"
                      style={{ fontFamily: "'Noto Sans Malayalam', sans-serif" }}
                    >
                      IRIS AI-നോട് ചോദിക്കൂ →
                    </motion.p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default AnimatedIntro;

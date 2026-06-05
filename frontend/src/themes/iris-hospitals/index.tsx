/**
 * iris-hospitals/index.tsx
 */

import 'regenerator-runtime/runtime';
import React, { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import AnimatedIntro from './AnimatedIntro';
import Chat from './Chat';
import { ShieldCheck } from 'lucide-react';

interface IrisThemeProps {
  hospitalId?: number;
  hospitalName?: string;
}

const IrisTheme: React.FC<IrisThemeProps> = ({ hospitalId, hospitalName }) => {
  const [showIntro, setShowIntro] = useState(true);

  return (
    <div
      className="min-h-screen w-full font-sans text-slate-900 overflow-x-hidden"
      style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)' }}
    >
      {/* ── Header ──────────────────────────────────────────────── */}
      <header
        className="border-b border-white/10 px-6 py-4 flex justify-between items-center sticky top-0 z-10 backdrop-blur-sm w-full"
        style={{ background: 'rgba(15,23,42,0.8)' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-xl shadow-md"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
          >
            I
          </div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            {hospitalName || (
              <>IRIS <span style={{ color: '#818cf8' }}>Hospitals</span></>
            )}
          </h1>
        </div>
        <div className="hidden md:flex items-center gap-2 text-xs text-slate-400 font-medium">
          <ShieldCheck className="w-4 h-4" style={{ color: '#818cf8' }} />
          Powered by Gothos Labs
        </div>
      </header>

      {/* ── Animated Intro → Chat ───────────────────────────────── */}
      <AnimatePresence mode="wait">
        {showIntro ? (
          <AnimatedIntro
            key="intro"
            onComplete={() => setShowIntro(false)}
            hospitalName={hospitalName}
          />
        ) : (
<main key="chat" className="w-full max-w-7xl mx-auto px-4 sm:px-6 py-4 pb-8">
              <div className="grid lg:grid-cols-2 gap-8 lg:gap-12 items-center">

                {/* Left — hero copy: hidden on mobile, visible on desktop */}
                <div className="space-y-5 hidden lg:block">
                <div
                  className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium"
                  style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc' }}
                >
                  <ShieldCheck className="w-4 h-4" /> AI-Powered Reception
                </div>
                <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold leading-tight text-white">
                  വിദഗ്ധ പരിചരണം, <br />
                  <span style={{ color: '#818cf8' }}>AI-സഹായത്തോടെ.</span>
                </h2>
                <p className="text-base sm:text-lg leading-relaxed" style={{ color: '#94a3b8' }}>
                  {hospitalName || 'IRIS Hospitals'}-ലേക്ക് സ്വാഗതം.{' '}
                  ഡോക്ടർ ലഭ്യത, അപ്പോയിന്റ്മെന്റ്, ലാബ് ടെസ്റ്റ് — ഇവ ഇംഗ്ലീഷിലോ മലയാളത്തിലോ ചോദിക്കൂ.
                </p>
                <ul className="space-y-2 text-sm" style={{ color: '#64748b' }}>
                  {[
                    '🩺 ഡോക്ടർ ലഭ്യത തൽക്കാലം അറിയുക',
                    '📅 ശബ്ദം കൊണ്ടോ ടെക്സ്റ്റ് കൊണ്ടോ അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യുക',
                    '💊 ഫാർമസി & ലാബ് ടെസ്റ്റ് വിവരങ്ങൾ',
                    '🌐 ഇംഗ്ലീഷ്, മലയാളം പിന്തുണ',
                  ].map(item => (
                    <li key={item} className="flex items-center gap-2">
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Right — Chat widget */}
    <div className="flex flex-col items-center lg:col-auto col-span-full">
      <Chat hospitalId={hospitalId?.toString() ?? ''} />
    </div>
            </div>
          </main>
        )}
      </AnimatePresence>
    </div>
  );
};

export default IrisTheme;

/**
 * iris-hospitals/index.tsx
 */

import 'regenerator-runtime/runtime';
import React, { useState } from 'react';
import { AnimatePresence, motion, MotionConfig } from 'framer-motion';
import AnimatedIntro from './AnimatedIntro';
import Chat from './Chat';
import { ShieldCheck } from 'lucide-react';
import irisLogo from './iris-logo.png';
import { fadeUp, stagger, DUR, EASE_IRIS } from './motion';

interface IrisThemeProps {
  hospitalId?: number;
  hospitalName?: string;
}

const IrisTheme: React.FC<IrisThemeProps> = ({ hospitalId, hospitalName }) => {
  const [showIntro, setShowIntro] = useState(true);
  const [introComplete, setIntroComplete] = useState(false);

  const handleIntroComplete = () => {
    setShowIntro(false);
    setIntroComplete(true);
  };

  return (
    <MotionConfig reducedMotion="user">
      <div className="min-h-screen w-full overflow-x-hidden bg-iris-surface bg-[image:var(--iris-bg-gradient)] font-[family-name:var(--font-iris-sans)]">
        {/* ── Header ──────────────────────────────────────────────── */}
        <header className="border-b border-iris-border px-6 py-4 flex justify-between items-center sticky top-0 z-10 w-full bg-iris-surface">
          <div className="flex items-center gap-3">
            <img
              src={irisLogo}
              alt={hospitalName || 'IRIS Hospitals'}
              width={256}
              height={75}
              fetchPriority="high"
              className="h-[41px] md:h-[44px] w-auto"
            />
            <h1 className="sr-only">{hospitalName || 'IRIS Hospitals'}</h1>
          </div>
          <div className="hidden md:flex items-center gap-2 text-xs text-iris-text-muted font-medium">
            <ShieldCheck className="w-4 h-4 text-iris-primary" />
            Powered by Gothos Labs
          </div>
        </header>

        {/* ── Animated Intro → Chat ───────────────────────────────── */}
        <AnimatePresence mode="wait">
          {showIntro ? (
            <AnimatedIntro
              key="intro"
              onComplete={handleIntroComplete}
              hospitalName={hospitalName}
            />
          ) : (
            <main key="chat" className="w-full max-w-7xl mx-auto px-4 sm:px-6 py-4 pb-8">
              <div className="grid lg:grid-cols-2 gap-8 lg:gap-12 items-center">

                {/* Left — hero copy: hidden on mobile, visible on desktop */}
                <div className="space-y-5 hidden lg:block">
                  {/* Hero panel */}
                  <div className="relative rounded-iris bg-iris-accent-surface p-7 lg:p-10">
                    {/* Decorative sage rectangle behind the panel's top-right corner */}
                    <div
                      aria-hidden="true"
                      className="absolute -top-4 -right-4 w-24 h-16 rounded-iris bg-iris-sage"
                    />

                    {/* Inner content above the decorative element */}
                    <div className="relative">
                      <motion.div
                        variants={stagger()}
                        initial="hidden"
                        animate={introComplete ? 'show' : 'hidden'}
                        className="space-y-5"
                      >
                        {/* Pill */}
                        <motion.div variants={fadeUp} className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-iris-surface-raised text-iris-primary text-[12px] font-semibold tracking-[0.08em] uppercase">
                          <ShieldCheck className="w-4 h-4" /> AI-Powered Reception
                        </motion.div>

                        {/* Headline */}
                        <motion.h2
                          variants={fadeUp}
                          className="font-[family-name:var(--font-iris-display)] font-light text-iris-text-primary text-iris-display-ml text-balance"
                        >
                          വിദഗ്ധ പരിചരണം, <br />
                          <span className="italic text-iris-primary">AI-സഹായത്തോടെ.</span>
                        </motion.h2>

                        {/* Paragraph */}
                        <motion.p variants={fadeUp} className="text-base sm:text-lg leading-relaxed text-iris-text-muted">
                          {hospitalName || 'IRIS Hospitals'}-ലേക്ക് സ്വാഗതം.{' '}
                          ഡോക്ടർ ലഭ്യത, അപ്പോയിന്റ്മെന്റ്, ലാബ് ടെസ്റ്റ് — ഇവ ഇംഗ്ലീഷിലോ മലയാളത്തിലോ ചോദിക്കൂ.
                        </motion.p>

                        {/* Bullets */}
                        <motion.ul variants={fadeUp} className="space-y-2 text-sm text-iris-text-muted">
                          {[
                            '🩺 ഡോക്ടർ ലഭ്യത തൽക്കാലം അറിയുക',
                            '📅 ശബ്ദം കൊണ്ടോ ടെക്സ്റ്റ് കൊണ്ടോ അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യുക',
                            '💊 ഫാർമസി & ലാബ് ടെസ്റ്റ് വിവരങ്ങൾ',
                            '🌐 ഇംഗ്ലീഷ്, മലയാളം പിന്തുണ',
                          ].map(item => (
                            <motion.li key={item} variants={fadeUp} className="flex items-center gap-2">
                              <span>{item}</span>
                            </motion.li>
                          ))}
                        </motion.ul>
                      </motion.div>
                    </div>
                  </div>
                </div>

                {/* Right — Chat widget */}
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={introComplete ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
                  transition={{ duration: DUR.slow, ease: EASE_IRIS }}
                  className="flex flex-col justify-center items-center w-full px-2 lg:col-auto col-span-full"
                >
                  <Chat hospitalId={hospitalId?.toString() ?? ''} />
                </motion.div>
              </div>
            </main>
          )}
        </AnimatePresence>
      </div>
    </MotionConfig>
  );
};

export default IrisTheme;

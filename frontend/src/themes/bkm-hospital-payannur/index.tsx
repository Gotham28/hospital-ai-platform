/**
 * bkm-hospital-payannur/index.tsx
 */
import 'regenerator-runtime/runtime';
import React from 'react';
import Chat from './Chat';
import { ShieldCheck } from 'lucide-react';

interface BkmThemeProps {
  hospitalId?: number;
  hospitalName?: string;
}

const BkmTheme: React.FC<BkmThemeProps> = ({ hospitalId, hospitalName }) => {
  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="bg-white border-b px-8 py-4 flex justify-between items-center sticky top-0 z-10 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-sky-500 rounded-lg flex items-center justify-center text-white font-bold text-xl shadow-md">
            B
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-800">
            {hospitalName || (
              <>BKM <span className="text-sky-500">Hospital</span></>
            )}
          </h1>
        </div>
        <div className="hidden md:flex items-center gap-2 text-xs text-slate-500 font-medium">
          <ShieldCheck className="w-4 h-4 text-sky-500" />
          Powered by Gothos Labs
        </div>
      </header>

      {/* ── Hero + Chat ──────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-6 py-12 grid lg:grid-cols-2 gap-12 items-center">
        {/* Left — Clean, minimal copy */}
        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-sky-100 text-sky-700 rounded-full text-sm font-medium">
            <ShieldCheck className="w-4 h-4" /> AI-Powered Reception
          </div>
          <h2 className="text-5xl font-extrabold leading-tight text-slate-800">
            Calm & Compassionate Care, <br />
            <span className="text-sky-500">Powered by AI.</span>
          </h2>
          <p className="text-lg text-slate-600 leading-relaxed">
            Welcome to the official portal for{' '}
            <strong>{hospitalName || 'BKM Hospital'}</strong>.
            Ask about doctors, book appointments, or check test details — in
            English or Malayalam.
          </p>
        </div>

        {/* Right — Chat widget */}
        <div className="flex flex-col items-center">
          <Chat hospitalId={hospitalId?.toString() ?? ''} />
        </div>
      </main>
    </div>
  );
};

export default BkmTheme;
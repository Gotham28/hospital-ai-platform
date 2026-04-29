/**
 * arogya-specialty/index.tsx
 * ─────────────────────────────────────────────────────────────────
 * AROGYA THEME — page wrapper / landing layout.
 *
 * Receives hospitalId + hospitalName from ThemeLoader.
 * Renders the branded header + hero section + Chat widget.
 *
 * ⚠️  Only UI here. No API calls. Logic lives in Chat → useChatCore.
 * ─────────────────────────────────────────────────────────────────
 */

import 'regenerator-runtime/runtime';
import React from 'react';
import Chat from './Chat';
import { ShieldCheck } from 'lucide-react';

interface ArogyaThemeProps {
  hospitalId?: number;
  hospitalName?: string;
}

const ArogyaTheme: React.FC<ArogyaThemeProps> = ({ hospitalId, hospitalName }) => {
  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">

      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="bg-white border-b px-8 py-4 flex justify-between items-center sticky top-0 z-10 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-emerald-600 rounded-lg flex items-center justify-center text-white font-bold text-xl shadow-md">
            A
          </div>

<h1 className="text-2xl font-bold tracking-tight text-slate-800">
  {hospitalName || (
    <>Arogya <span className="text-emerald-600">Specialty</span></>
  )}
</h1>
        </div>
        <div className="hidden md:flex items-center gap-2 text-xs text-slate-500 font-medium">
          <ShieldCheck className="w-4 h-4 text-emerald-500" />
          Powered by Gothos Labs
        </div>
      </header>

      {/* ── Hero + Chat ──────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-6 py-12 grid lg:grid-cols-2 gap-12 items-center">

        {/* Left — copy */}
        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-sm font-medium">
            <ShieldCheck className="w-4 h-4" /> AI-Powered Reception
          </div>
          <h2 className="text-5xl font-extrabold leading-tight text-slate-800">
            Advanced Care, <br />
            <span className="text-emerald-600">Voice-Enabled AI.</span>
          </h2>
          <p className="text-lg text-slate-600 leading-relaxed">
            Welcome to the official portal for{' '}
            <strong>{hospitalName || 'Arogya Specialty'}</strong>.
            Ask about doctors, book appointments, or check test details — in
            English or Malayalam.
          </p>
          <ul className="space-y-2 text-sm text-slate-500">
            {[
              '🩺 Real-time doctor availability',
              '📅 Book appointments by voice or text',
              '💊 Pharmacy & lab test lookup',
              '🌐 English & Malayalam support',
            ].map(item => (
              <li key={item} className="flex items-center gap-2">
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Right — Chat widget */}
        <div className="flex flex-col items-center">
          <Chat hospitalId={hospitalId?.toString() ?? ''} />
        </div>
      </main>
    </div>
  );
};

export default ArogyaTheme;
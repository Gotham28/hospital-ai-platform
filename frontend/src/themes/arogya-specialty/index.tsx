import 'regenerator-runtime/runtime'; 
import React from 'react';
import Chat from './Chat'; 
import { ShieldCheck, Activity } from 'lucide-react';

// REMOVE: import ReactDOM from 'react-dom/client'; <-- This belongs in main.tsx, not here.

interface ArogyaThemeProps {
  hospitalId?: number;
  hospitalName?: string;
}

const ArogyaTheme: React.FC<ArogyaThemeProps> = ({ hospitalId, hospitalName }) => {
  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
      <header className="bg-white border-b px-8 py-4 flex justify-between items-center sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 bg-emerald-600 rounded-lg flex items-center justify-center text-white font-bold text-xl">A</div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-800">
            {hospitalName || 'Arogya'} <span className="text-emerald-600">Specialty</span>
          </h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-12 grid lg:grid-cols-2 gap-12 items-center">
        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-sm font-medium">
            <ShieldCheck className="w-4 h-4" /> Powered by Gothos Labs
          </div>
          <h2 className="text-5xl font-extrabold leading-tight">
            Advanced Care, <br />
            <span className="text-emerald-600">Voice-Enabled AI.</span>
          </h2>
          <p className="text-lg text-slate-600">
            Welcome to the official portal for {hospitalName}. Experience the future of healthcare with our regional voice assistant.
          </p>
        </div>

        <div className="flex flex-col items-center">
          {/* Ensure hospitalId is passed correctly to the Chat logic */}
          <Chat hospitalId={hospitalId?.toString() || ""} />
        </div>
      </main>
    </div>
  );
};

export default ArogyaTheme;
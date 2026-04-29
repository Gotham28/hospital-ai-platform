/**
 * bkm-hospital-payannur/index.tsx
 * ─────────────────────────────────────────────────────────────────
 * BKM HOSPITAL THEME — page wrapper / landing layout.
 *
 * Design: Sapphire & Amber dark mode.
 * Uses SharedChat (from common) for the chat widget — no custom
 * Chat component needed because BKM uses text-only chat.
 *
 * To add voice/mic to BKM in future: create bkm-hospital-payannur/Chat.tsx
 * using useChatCore(), and replace <SharedChat> below with <Chat>.
 *
 * ⚠️  ONLY UI here. Zero logic, zero API calls.
 * ─────────────────────────────────────────────────────────────────
 */

import React from 'react';
import { SharedChat } from '../../components/common/SharedChat';
import './bkm-hospital.css';

interface BkmThemeProps {
  hospitalId?: number;
  hospitalName?: string;
}

const BkmTheme: React.FC<BkmThemeProps> = ({ hospitalId, hospitalName }) => {
  return (
    <div className="bkm-theme-wrapper">

      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="bkm-header flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Logo mark */}
          <div
            style={{
              width: 44, height: 44,
              background: 'linear-gradient(135deg, #1e3a8a, #06b6d4)',
              borderRadius: 10,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 900, fontSize: 20, color: '#f8fafc',
              boxShadow: '0 0 16px rgba(6,182,212,0.35)',
            }}
          >
            B
          </div>
          <div>
            <div className="bkm-logo-text">
              {hospitalName ?? 'BKM Hospital'}{' '}
              <span className="bkm-logo-accent">Payannur</span>
            </div>
            <div className="bkm-header-tagline">AI Patient Assistant</div>
          </div>
        </div>

        {/* Status pill */}
        <div className="bkm-badge" style={{ fontSize: '0.7rem', letterSpacing: '0.06em' }}>
          ● Online
        </div>
      </header>

      {/* ── Main content ─────────────────────────────────────────── */}
      <main
        style={{
          maxWidth: 1100,
          margin: '0 auto',
          padding: '3rem 1.5rem',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '2rem',
          alignItems: 'start',
        }}
      >
        {/* Left — info cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

          <div className="bkm-card">
            <div className="bkm-card-header">
              <span className="bkm-card-title">About</span>
              <span className="bkm-badge">Established</span>
            </div>
            <p style={{ fontSize: '0.875rem', color: 'var(--bkm-text-muted)', lineHeight: 1.7 }}>
              BKM Hospital, Payannur — a trusted multi-specialty hospital serving
              North Kerala. Ask our AI assistant about doctors, availability,
              appointments, and more.
            </p>
          </div>

          <div className="bkm-card">
            <div className="bkm-card-header">
              <span className="bkm-card-title">Quick Actions</span>
            </div>
            <ul style={{ fontSize: '0.875rem', color: 'var(--bkm-text-muted)', lineHeight: 2 }}>
              {[
                '🩺 Check doctor availability',
                '📅 Book an appointment',
                '💊 Pharmacy enquiry',
                '🔬 Lab test information',
              ].map(item => <li key={item}>{item}</li>)}
            </ul>
          </div>

          <div className="bkm-card">
            <div className="bkm-card-header">
              <span className="bkm-card-title">Contact</span>
              <span className="bkm-badge priority">Reception</span>
            </div>
            <p style={{ fontSize: '0.875rem', color: 'var(--bkm-text-muted)' }}>
              For urgent enquiries, call the reception desk directly.
              The AI assistant handles general queries 24 × 7.
            </p>
          </div>
        </div>

        {/* Right — Chat */}
        <div style={{ height: '70vh', minHeight: 480 }}>
          <SharedChat hospitalId={hospitalId ?? 0} />
        </div>
      </main>
    </div>
  );
};

export default BkmTheme;
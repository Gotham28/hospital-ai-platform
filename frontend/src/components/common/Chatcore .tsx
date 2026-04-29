/**
 * ChatCore.tsx
 * ─────────────────────────────────────────────────────────────────
 * Single source of truth for ALL chat logic shared across every
 * hospital theme. Themes import this and only supply their own UI.
 *
 * Exports:
 *   useChatCore(hospitalId)   – the shared logic hook
 *   ChatCoreProps             – interface for theme wrapper components
 * ─────────────────────────────────────────────────────────────────
 */

import { useState, useEffect, useRef } from 'react';
import { useHospitalChat } from '../../hooks/useHospitalChat';

// ── Types ────────────────────────────────────────────────────────

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
}

export type MicState = 'idle' | 'recording' | 'transcribing';
export type Language = 'en' | 'ml';

/** Props every theme's Chat component receives from its parent index.tsx */
export interface ChatCoreProps {
  hospitalId: string;
}

// ── Hook ─────────────────────────────────────────────────────────

/**
 * useChatCore
 *
 * Wraps useHospitalChat and exposes a typed, stable surface for
 * any theme to consume.  All business logic (API calls, VAD, STT,
 * streaming, translation) lives in useHospitalChat; this hook
 * simply re-exports it with clear typing.
 */
export function useChatCore(hospitalId: string) {
  const chat = useHospitalChat(hospitalId);

  // Auto-scroll ref — each theme can attach this to their scroll target
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat.messages]);

  return {
    // State
    language: chat.language as Language,
    setLanguage: chat.setLanguage,
    messages: chat.messages as Message[],
    isStreaming: chat.isStreaming,
    inputText: chat.inputText,
    setInputText: chat.setInputText,
    micState: chat.micState as MicState,
    micError: chat.micError,
    suggestions: chat.suggestions as { en: string[]; ml: string[] },
    vadLoading: chat.vadLoading,

    // Actions
    handleSend: chat.handleSend,
    toggleMic: chat.toggleMic,

    // Utility
    scrollRef,
  };
}
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { useHospitalChat } from './useHospitalChat';

// The mic/VAD library touches WASM assets and mic permissions that don't
// exist in jsdom; useHospitalChat imports it at module scope, so it has to
// be mocked before the hook can even render in a test environment.
vi.mock('@ricky0123/vad-react', () => ({
  useMicVAD: () => ({ loading: false, errored: false, start: vi.fn(), pause: vi.fn() }),
  utils: { encodeWAV: vi.fn() },
}));

// The two hardcoded wordings from useHospitalChat.tsx's STREAM_FALLBACK_MESSAGE,
// approved by the developer 2026-09-04. Duplicated here deliberately — if the
// literal ever drifts, this test should fail rather than silently pass by
// importing the same constant it's meant to be checking.
const FALLBACK_EN = "Sorry, I couldn't answer that just now. Please try again.";
const FALLBACK_ML = "ക്ഷമിക്കണം, ഇപ്പോൾ ഉത്തരം നൽകാൻ കഴിഞ്ഞില്ല. ദയവായി വീണ്ടും ശ്രമിക്കുക.";

function sseFrame(rawPayload: string): string {
  return `data: ${rawPayload}\n\n`;
}

function contentFrame(text: string): string {
  return sseFrame(JSON.stringify(text));
}

function makeSSEResponse(frames: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const f of frames) {
        controller.enqueue(encoder.encode(f));
      }
      controller.close();
    },
  });
  return new Response(body, { status: 200 });
}

// Minimal harness exposing exactly what a real theme's Chat.tsx exposes:
// a text input bound to inputText, a send button calling handleSend(), a
// rendered list of messages (assert against THIS, not hook internals), and
// two buttons to flip the language toggle real users have.
function ChatHarness({ hospitalId }: { hospitalId: string }) {
  const chat = useHospitalChat(hospitalId);
  return (
    <div>
      <button onClick={() => chat.setLanguage('en')}>set-en</button>
      <button onClick={() => chat.setLanguage('ml')}>set-ml</button>
      <input
        aria-label="message-input"
        value={chat.inputText}
        onChange={(e) => chat.setInputText(e.target.value)}
      />
      <button onClick={() => chat.handleSend()}>send</button>
      <div aria-label="messages">
        {chat.messages.map((m, i) => (
          <div key={i} data-role={m.role} data-testid={`message-${i}`}>
            {m.content}
          </div>
        ))}
      </div>
    </div>
  );
}

async function sendMessage(text: string) {
  fireEvent.change(screen.getByLabelText('message-input'), { target: { value: text } });
  fireEvent.click(screen.getByText('send'));
}

function lastMessage(): HTMLElement {
  const all = screen.getAllByTestId(/^message-/);
  return all[all.length - 1];
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  window.sessionStorage.clear();
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function mockChatStreamFrames(frames: string[]) {
  fetchMock = vi.fn((url: string) => {
    if (typeof url === 'string' && url.includes('/ai/chat-stream')) {
      return Promise.resolve(makeSSEResponse(frames));
    }
    // welcome/suggestions fetches — hook treats a non-ok response as a no-op
    return Promise.resolve(new Response(null, { status: 404 }));
  });
  vi.stubGlobal('fetch', fetchMock);
}

describe('useHospitalChat — chat-stream SSE consumption (A5)', () => {
  it('shows the fallback when the stream emits [STREAM_ERROR] then [DONE]', async () => {
    mockChatStreamFrames([sseFrame('[STREAM_ERROR]'), sseFrame('[DONE]')]);
    render(<ChatHarness hospitalId="1" />);

    await sendMessage('which doctors are available');

    await waitFor(() => {
      expect(lastMessage()).toHaveTextContent(FALLBACK_ML); // default language is 'ml'
    });
  });

  it('shows the fallback when the stream ends with [DONE] and zero content', async () => {
    mockChatStreamFrames([sseFrame('[DONE]')]);
    render(<ChatHarness hospitalId="1" />);

    await sendMessage('which doctors are available');

    await waitFor(() => {
      expect(lastMessage()).toHaveTextContent(FALLBACK_ML);
    });
  });

  it('discards partial content and replaces it with the fallback when [STREAM_ERROR] follows it', async () => {
    mockChatStreamFrames([
      contentFrame('Dr. '),
      contentFrame('Anjali is '),
      sseFrame('[STREAM_ERROR]'),
      sseFrame('[DONE]'),
    ]);
    render(<ChatHarness hospitalId="1" />);

    await sendMessage('which doctors are available');

    await waitFor(() => {
      const el = lastMessage();
      expect(el).toHaveTextContent(FALLBACK_ML);
      expect(el).not.toHaveTextContent('Dr. Anjali is');
    });
  });

  it('renders the answer unchanged, with no fallback, on a normal completed stream', async () => {
    mockChatStreamFrames([
      contentFrame('Dr. Anjali is '),
      contentFrame('available today.'),
      sseFrame('[DONE]'),
    ]);
    render(<ChatHarness hospitalId="1" />);

    await sendMessage('which doctors are available');

    await waitFor(() => {
      expect(lastMessage()).toHaveTextContent('Dr. Anjali is available today.');
    });
    expect(lastMessage()).not.toHaveTextContent(FALLBACK_ML);
    expect(lastMessage()).not.toHaveTextContent(FALLBACK_EN);
  });
});

describe('useHospitalChat — fallback wording follows the language toggle (A6/Step 3)', () => {
  it('shows the English fallback when language is en', async () => {
    mockChatStreamFrames([sseFrame('[DONE]')]);
    render(<ChatHarness hospitalId="1" />);

    fireEvent.click(screen.getByText('set-en'));
    await sendMessage('which doctors are available');

    await waitFor(() => {
      expect(lastMessage()).toHaveTextContent(FALLBACK_EN);
    });
  });

  it('shows the Malayalam fallback when language is ml', async () => {
    mockChatStreamFrames([sseFrame('[DONE]')]);
    render(<ChatHarness hospitalId="1" />);

    fireEvent.click(screen.getByText('set-ml'));
    await sendMessage('ഏത് ഡോക്ടർമാരുണ്ട്');

    await waitFor(() => {
      expect(lastMessage()).toHaveTextContent(FALLBACK_ML);
    });
  });
});

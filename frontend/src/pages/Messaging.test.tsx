import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import MessagingPage from './Messaging';

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('../api/axios', () => ({ default: api }));
const config = {
  enabled: true, assistant_url: 'https://example.test/p/synthetic',
  templates: { en: { preview: 'Synthetic English welcome' }, ml: { preview: 'പരീക്ഷണ സന്ദേശം' } },
};
const accepted = { message_id: 7, masked_phone: '********3210', language: 'en', status: 'accepted', error_code: null };

function mount() {
  return render(<MemoryRouter initialEntries={['/hospitals/1/messaging']}><Routes>
    <Route path="/hospitals/:hospitalId/messaging" element={<MessagingPage />} />
  </Routes></MemoryRouter>);
}
async function ready() {
  mount(); await screen.findByText('Synthetic English welcome');
}
function fill() {
  fireEvent.change(screen.getByLabelText('Patient mobile number'), { target: { value: '9876543210' } });
  fireEvent.click(screen.getByRole('checkbox'));
}
function submit() {
  fireEvent.submit(screen.getByLabelText('Patient mobile number').closest('form')!);
}

beforeEach(() => {
  vi.useRealTimers(); api.get.mockReset(); api.post.mockReset();
  api.get.mockImplementation((path: string) => Promise.resolve({ data: path.endsWith('welcome-config') ? config : accepted }));
  api.post.mockResolvedValue({ data: accepted });
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe('Meta patient welcomes', () => {

  it('cancels an old recipient refresh without blocking the next patient polling', async () => {
    await ready(); vi.useFakeTimers(); fill(); submit(); await act(async () => {});
    let resolveOld: (value: { data: typeof accepted }) => void = () => {};
    const next = { ...accepted, message_id: 8, masked_phone: '********0123' };
    api.get.mockImplementation((path: string) => path.endsWith('/7')
      ? new Promise(done => { resolveOld = done; })
      : Promise.resolve({ data: { ...next, status: 'delivered' } }));
    fireEvent.click(screen.getByRole('button', { name: 'Refresh status' }));
    const oldSignal = api.get.mock.calls.at(-1)![1].signal as AbortSignal;
    fireEvent.change(screen.getByLabelText('Patient mobile number'), { target: { value: '+12025550123' } });
    expect(oldSignal.aborted).toBe(true);
    api.post.mockResolvedValueOnce({ data: next });
    fireEvent.click(screen.getByRole('checkbox')); submit(); await act(async () => {});
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(screen.getByText('Message delivered.')).toBeInTheDocument();
    expect(screen.getByText('Recipient: ********0123')).toBeInTheDocument();
    await act(async () => { resolveOld({ data: { ...accepted, status: 'read' } }); });
    expect(screen.getByText('Message delivered.')).toBeInTheDocument();
    expect(screen.getByText('Recipient: ********0123')).toBeInTheDocument();
  });


  it('waits for slow automatic and manual status requests before polling again', async () => {
    await ready(); vi.useFakeTimers(); fill(); submit(); await act(async () => {});
    const resolves: Array<(value: { data: typeof accepted }) => void> = [];
    api.get.mockImplementation(() => new Promise(done => { resolves.push(done); }));
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(resolves).toHaveLength(1);
    await act(async () => { resolves[0]({ data: { ...accepted, status: 'sent' } }); });
    expect(screen.getByText('Message sent. Waiting for delivery confirmation.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Refresh status' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(resolves).toHaveLength(2);
    await act(async () => { resolves[1]({ data: { ...accepted, status: 'delivered' } }); });
    expect(screen.getByText('Message delivered.')).toBeInTheDocument();
  });


  it.each(['failed', 'unknown'])('resets language for a new patient after %s', async status => {
    api.post.mockResolvedValue({ data: { ...accepted, language: 'ml', status } });
    await ready();
    fireEvent.change(screen.getByLabelText('Message language'), { target: { value: 'ml' } });
    fill(); submit(); await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    await act(async () => {});
    expect(screen.getByLabelText('Message language')).toHaveValue('ml');
    fireEvent.change(screen.getByLabelText('Patient mobile number'), { target: { value: '+12025550123' } });
    expect(screen.getByLabelText('Message language')).toHaveValue('en');
    expect(screen.getByRole('checkbox')).not.toBeChecked();
  });

  it('preserves Malayalam and request key for an unchanged uncertain retry', async () => {
    api.post.mockRejectedValueOnce(new Error('Synthetic lost response'));
    await ready();
    fireEvent.change(screen.getByLabelText('Message language'), { target: { value: 'ml' } });
    fill(); submit(); await screen.findByRole('alert');
    const key = api.post.mock.calls[0][1].request_id;
    expect(screen.getByLabelText('Message language')).toHaveValue('ml');
    submit(); await screen.findByText('Meta accepted the message. Delivery is not yet confirmed.');
    expect(api.post.mock.calls[1][1]).toMatchObject({ language: 'ml', request_id: key });
  });

  it('rejects reversed manual responses and stale states after polling expires', async () => {
    await ready(); vi.useFakeTimers(); fill(); submit(); await act(async () => {});
    await act(async () => { await vi.advanceTimersByTimeAsync(125_000); });
    expect(screen.getByText('Automatic status checks have ended.')).toBeInTheDocument();
    const resolves: Array<(value: { data: typeof accepted }) => void> = [];
    api.get.mockImplementation(() => new Promise(done => { resolves.push(done); }));
    fireEvent.click(screen.getByRole('button', { name: 'Refresh status' }));
    fireEvent.click(screen.getByRole('button', { name: 'Refresh status' }));
    expect(resolves).toHaveLength(2);
    await act(async () => { resolves[1]({ data: { ...accepted, status: 'read' } }); });
    await act(async () => { resolves[0]({ data: accepted }); });
    expect(screen.getByText('Message read.')).toBeInTheDocument();
    api.get.mockResolvedValue({ data: accepted });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh status' }));
    await act(async () => {});
    expect(screen.getByText('Message read.')).toBeInTheDocument();
  });

  it('reconciles failure to delivery and ignores a late overlapping poll', async () => {
    await ready(); vi.useFakeTimers(); fill(); submit(); await act(async () => {});
    const resolves: Array<(value: { data: typeof accepted }) => void> = [];
    api.get.mockImplementation(() => new Promise(done => { resolves.push(done); }));
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh status' }));
    await act(async () => { resolves[1]({ data: { ...accepted, status: 'failed' } }); });
    expect(screen.getByText('Message could not be delivered. Check the sender and template setup.')).toBeInTheDocument();
    await act(async () => { resolves[0]({ data: accepted }); });
    expect(screen.getByText('Message could not be delivered. Check the sender and template setup.')).toBeInTheDocument();
    api.get.mockResolvedValue({ data: { ...accepted, status: 'delivered' } });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh status' }));
    await act(async () => {});
    expect(screen.getByText('Message delivered.')).toBeInTheDocument();
  });

  it('does not send while typing and requires permission', async () => {
    await ready();
    const button = screen.getByRole('button', { name: 'Send welcome' });
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Patient mobile number'), { target: { value: '9876543210' } });
    expect(button).toBeDisabled(); expect(api.post).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('checkbox'));
    expect(button).toBeEnabled(); submit();
    await screen.findByText('Meta accepted the message. Delivery is not yet confirmed.');
    expect(api.post).toHaveBeenCalledWith('/hospitals/1/whatsapp/send-welcome', {
      phone: '9876543210', language: 'en', consent_confirmed: true, request_id: expect.any(String),
    });
    expect(screen.getByLabelText('Patient mobile number')).toHaveValue('');
    expect(screen.getByRole('checkbox')).not.toBeChecked();
  });

  it('uses selected Malayalam preview and submits exactly one language', async () => {
    await ready();
    fireEvent.change(screen.getByLabelText('Message language'), { target: { value: 'ml' } });
    expect(screen.getByText('പരീക്ഷണ സന്ദേശം')).toBeInTheDocument();
    fill(); submit(); await waitFor(() => expect(api.post).toHaveBeenCalled());
    expect(api.post.mock.calls[0][1].language).toBe('ml');
    await screen.findByText('Meta accepted the message. Delivery is not yet confirmed.');
    expect(screen.getByLabelText('Message language')).toHaveValue('en');
  });

  it('disables sending when setup is missing and never falls back to legacy send', async () => {
    api.get.mockResolvedValue({ data: { enabled: false, templates: {} } });
    mount(); await screen.findByText(/WhatsApp is not ready/);
    fill(); expect(screen.getByRole('button', { name: 'Send welcome' })).toBeDisabled();
    submit(); expect(api.post).not.toHaveBeenCalled();
  });

  it('prevents simultaneous submits, including Enter submit events', async () => {
    let resolve: (result: { data: typeof accepted }) => void = () => {};
    api.post.mockImplementation(() => new Promise(done => { resolve = done; }));
    await ready(); fill(); submit(); submit();
    expect(api.post).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Submitting…' })).toBeDisabled();
    await act(async () => { resolve({ data: accepted }); });
  });

  it('retains the recipient and request ID on an uncertain network response', async () => {
    api.post.mockRejectedValueOnce(new Error('Synthetic network failure'));
    await ready(); fill(); submit();
    await screen.findByRole('alert');
    expect(screen.getByLabelText('Patient mobile number')).toHaveValue('9876543210');
    const key = api.post.mock.calls[0][1].request_id;
    submit(); await screen.findByText('Meta accepted the message. Delivery is not yet confirmed.');
    expect(api.post.mock.calls[1][1].request_id).toBe(key);
  });

  it('keeps uncertain submission locked and offers a status check', async () => {
    api.post.mockResolvedValue({ data: { ...accepted, status: 'unknown' } });
    await ready(); fill(); submit();
    await screen.findByText('Submission is uncertain. Check its status before sending again.');
    expect(screen.getByRole('button', { name: 'Send welcome' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Refresh status' }));
    await screen.findByText('Meta accepted the message. Delivery is not yet confirmed.');
    expect(api.post).toHaveBeenCalledTimes(1);
  });

  it('polls delivery, expires after two minutes and supports manual refresh', async () => {
    await ready(); vi.useFakeTimers(); fill(); submit();
    await act(async () => {});
    api.get.mockResolvedValue({ data: { ...accepted, status: 'delivered' } });
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(screen.getByText('Message delivered.')).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(125_000); });
    expect(screen.getByText('Automatic status checks have ended.')).toBeInTheDocument();
    const calls = api.get.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    expect(api.get).toHaveBeenCalledTimes(calls);
    api.get.mockResolvedValue({ data: { ...accepted, status: 'read' } });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh status' }));
    await act(async () => {});
    expect(screen.getByText('Message read.')).toBeInTheDocument();
  });

  it('cancels polling when recipient changes and on unmount', async () => {
    await ready(); vi.useFakeTimers(); fill(); submit();
    await act(async () => {});
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    fireEvent.change(screen.getByLabelText('Patient mobile number'), { target: { value: '+12025550123' } });
    const count = api.get.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    expect(api.get).toHaveBeenCalledTimes(count);
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    fireEvent.click(screen.getByRole('checkbox')); submit(); await act(async () => {});
    cleanup(); const before = api.get.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    expect(api.get).toHaveBeenCalledTimes(before);
  });
});

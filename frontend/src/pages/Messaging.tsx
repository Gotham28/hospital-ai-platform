import React, { useEffect, useRef, useState } from 'react';
import { isAxiosError } from 'axios';
import { useParams } from 'react-router-dom';
import { MessageSquare, Send, Upload, FileSpreadsheet, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import api from '../api/axios';

type Language = 'en' | 'ml';
type MessageState = {
  message_id: number; masked_phone: string; language: Language;
  status: 'pending' | 'accepted' | 'sent' | 'delivered' | 'read' | 'failed' | 'unknown';
  error_code: string | null;
};
function latestState(previous: MessageState | undefined, next: MessageState): MessageState {
  if (!previous || previous.message_id !== next.message_id) return next;
  const rank = { pending: 0, unknown: 0, accepted: 1, sent: 2, failed: 2.5, delivered: 3, read: 4 };
  return rank[next.status] < rank[previous.status] ? previous : next;
}

type WelcomeConfig = {
  enabled: boolean; assistant_url?: string;
  templates: Partial<Record<Language, { preview: string }>>;
};
const messageLabels: Record<MessageState['status'], string> = {
  pending: 'Submission pending. Check its status before sending again.',
  accepted: 'Meta accepted the message. Delivery is not yet confirmed.',
  sent: 'Message sent. Waiting for delivery confirmation.',
  delivered: 'Message delivered.', read: 'Message read.',
  failed: 'Message could not be delivered. Check the sender and template setup.',
  unknown: 'Submission is uncertain. Check its status before sending again.',
};
const terminalStates = new Set(['read', 'failed']);

export default function MessagingPage() {
  const { hospitalId } = useParams();
  return <HospitalMessaging key={hospitalId} hospitalId={hospitalId ?? ''} />;
}

function HospitalMessaging({ hospitalId }: { hospitalId: string }) {
  
  const [singlePhone, setSinglePhone] = useState('');
  const [language, setLanguage] = useState<Language>('en');
  const [permission, setPermission] = useState(false);
  const [isSendingSingle, setIsSendingSingle] = useState(false);
  const [singleError, setSingleError] = useState<string | null>(null);
  const [configState, setConfigState] = useState<{ hospitalId: string; config: WelcomeConfig } | null>(null);
  const [messageState, setMessageState] = useState<{ hospitalId: string; message: MessageState } | null>(null);
  const [pollExpired, setPollExpired] = useState(false);
  const pending = useRef(false);
  const requestKey = useRef<{ id: string; payload: string } | null>(null);
  const currentHospital = useRef(hospitalId);
  useEffect(() => { currentHospital.current = hospitalId; }, [hospitalId]);
  const recipientVersion = useRef(0);
  const statusSequence = useRef(0);
  const statusInFlight = useRef({ count: 0 });
  const manualControllers = useRef(new Set<AbortController>());
  useEffect(() => {
    const controllers = manualControllers.current;
    return () => {
      recipientVersion.current += 1; statusSequence.current += 1;
      controllers.forEach(controller => controller.abort()); controllers.clear();
    };
  }, []);
  const pollWindow = useRef<{ id: number; expires: number } | null>(null);
  const config = configState?.hospitalId === hospitalId ? configState.config : null;
  const message = messageState?.hospitalId === hospitalId ? messageState.message : null;

  useEffect(() => {
    let active = true;
    api.get<WelcomeConfig>(`/hospitals/${hospitalId}/whatsapp/welcome-config`)
      .then(res => { if (active) setConfigState({ hospitalId: hospitalId ?? '', config: res.data }); })
      .catch(() => { if (active) setConfigState({ hospitalId: hospitalId ?? '', config: { enabled: false, templates: {} } }); });
    return () => { active = false; };
  }, [hospitalId]);

  const messageId = message?.message_id;
  const messageStatus = message?.status;
  useEffect(() => {
    if (!messageId || !messageStatus || terminalStates.has(messageStatus)) return;
    let active = true;
    const controller = new AbortController();
    if (pollWindow.current?.id !== messageId) pollWindow.current = { id: messageId, expires: Date.now() + 120_000 };
    const expires = pollWindow.current.expires;
    const timer = window.setInterval(async () => {
      if (Date.now() >= expires) {
        window.clearInterval(timer);
        if (active) setPollExpired(true);
        return;
      }
      if (statusInFlight.current.count > 0) return;
      const sequence = ++statusSequence.current;
      const flightGroup = statusInFlight.current;
      flightGroup.count += 1;
      try {
        const res = await api.get<MessageState>(`/hospitals/${hospitalId}/whatsapp/messages/${messageId}`, { signal: controller.signal });
        if (active && sequence === statusSequence.current) setMessageState(previous => ({ hospitalId: hospitalId ?? '', message: latestState(previous?.message, res.data) }));
      } catch { /* Keep the last known state; manual refresh remains available. */ }
      finally { flightGroup.count -= 1; }
    }, 5000);
    return () => { active = false; controller.abort(); window.clearInterval(timer); };
  }, [hospitalId, messageId, messageStatus]);

  const resetRecipient = (phone: string, nextLanguage: Language = (message || requestKey.current) ? 'en' : language) => {
    setLanguage(nextLanguage);
    statusSequence.current += 1;
    setSinglePhone(phone);
    setPermission(false);
    setSingleError(null);
    setMessageState(null);
    setPollExpired(false);
    recipientVersion.current += 1;
    manualControllers.current.forEach(controller => controller.abort());
    manualControllers.current.clear();
    // Old promises own their detached counter; they cannot block the next recipient.
    statusInFlight.current = { count: 0 };
    // Preserve a request key on a same-recipient network retry; editing starts a new intent.
    requestKey.current = null;
  };

  const handleSendSingle = async (event: React.FormEvent) => {
    event.preventDefault();
    if (pending.current || !config?.enabled || !singlePhone.trim() || !permission || !config.templates[language]) return;
    pending.current = true;
    setIsSendingSingle(true);
    setSingleError(null);
    const payload = JSON.stringify([hospitalId, singlePhone.trim(), language]);
    if (requestKey.current?.payload !== payload) requestKey.current = { id: crypto.randomUUID(), payload };
    const targetHospital = hospitalId;
    const version = recipientVersion.current;
    try {
      const res = await api.post<MessageState>(`/hospitals/${hospitalId}/whatsapp/send-welcome`, {
        phone: singlePhone.trim(), language, consent_confirmed: permission, request_id: requestKey.current.id,
      });
      if (currentHospital.current !== targetHospital || recipientVersion.current !== version) return;
      setMessageState({ hospitalId: hospitalId ?? '', message: res.data });
      setPollExpired(false);
      if (['accepted', 'sent', 'delivered', 'read'].includes(res.data.status)) {
        setSinglePhone(''); setPermission(false); setLanguage('en'); requestKey.current = null;
      }
    } catch (error: unknown) {
      if (currentHospital.current !== targetHospital || recipientVersion.current !== version) return;
      const code = isAxiosError(error) ? error.response?.data?.detail?.code : undefined;
      const labels: Record<string, string> = {
        invalid_phone: 'Enter a valid mobile number, including a country code for numbers outside India.',
        permission_required: 'Confirm that the patient agreed to receive this WhatsApp message.',
        setup_required: 'WhatsApp setup is incomplete. Ask the platform administrator to complete it.',
        request_conflict: 'This submission has changed. Check its previous status before continuing.',
        submission_unknown: 'Submission is uncertain. Use the same unchanged form to check the request; do not start a new send.',
      };
      setSingleError(labels[code] ?? 'Unable to confirm submission. Retry the unchanged form to check the same request.');
    } finally { pending.current = false; setIsSendingSingle(false); }
  };

  const refreshStatus = async () => {
    if (!message) return;
    const id = message.message_id;
    const sequence = ++statusSequence.current;
    const flightGroup = statusInFlight.current;
    flightGroup.count += 1;
    const controller = new AbortController();
    manualControllers.current.add(controller);
    const version = recipientVersion.current;
    try {
      const res = await api.get<MessageState>(`/hospitals/${hospitalId}/whatsapp/messages/${id}`, { signal: controller.signal });
      if (recipientVersion.current === version && currentHospital.current === hospitalId && sequence === statusSequence.current) {
        setMessageState(previous => ({ hospitalId: hospitalId ?? '', message: latestState(previous?.message, res.data) }));
      }
    } catch {
      if (recipientVersion.current === version && currentHospital.current === hospitalId && sequence === statusSequence.current) {
        setSingleError('Status is unavailable. Try checking again later.');
      }
    } finally { flightGroup.count -= 1; manualControllers.current.delete(controller); }
  };

  // Bulk Message State
  const [bulkFile, setBulkFile] = useState<File | null>(null);
  const [bulkTemplate, setBulkTemplate] = useState('');
  const [isSendingBulk, setIsSendingBulk] = useState(false);
  const [bulkStatus, setBulkStatus] = useState<{
    type: 'success' | 'error';
    msg: string;
    details?: { sent: number; failed: number; errors: string[] };
  } | null>(null);

  const handleBulkUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bulkFile || !bulkTemplate) return;

    setIsSendingBulk(true);
    setBulkStatus(null);
    const formData = new FormData();
    formData.append('file', bulkFile);
    formData.append('message_template', bulkTemplate);

    try {
      const res = await api.post(`/hospitals/${hospitalId}/whatsapp/send-bulk`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setBulkStatus({ 
        type: 'success', 
        msg: 'Bulk processing completed!',
        details: res.data 
      });
      setBulkFile(null);
      setBulkTemplate('');
    } catch (err: unknown) {
      setBulkStatus({ 
        type: 'error', 
        msg: (isAxiosError(err) && typeof err.response?.data?.detail === 'string') ? err.response.data.detail : 'Failed to process bulk upload' 
      });
    } finally {
      setIsSendingBulk(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <MessageSquare className="w-6 h-6 text-blue-600" /> Patient Messaging
        </h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* One approved Meta template, selected for this patient. */}
        <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-100 bg-gray-50 px-6 py-4">
            <h2 className="text-lg font-bold text-gray-800">Send patient welcome</h2>
            <p className="text-sm text-gray-500 mt-1">A welcome from Arogya with this hospital's assistant link.</p>
          </div>
          <div className="p-6">
            <form onSubmit={handleSendSingle} className="space-y-4">
              {!config && <p role="status">Loading WhatsApp setup…</p>}
              {config && !config.enabled && <p role="status" className="text-sm text-amber-800">WhatsApp is not ready for this hospital. Ask the platform administrator to complete setup.</p>}
              {singleError && <p role="alert" className="text-sm text-red-700">{singleError}</p>}
              {message && <div role="status" className="text-sm bg-gray-50 p-3 rounded-lg">
                <p>{messageLabels[message.status]}</p>
                <p className="mt-1 text-gray-500">Recipient: {message.masked_phone}</p>
                {pollExpired && <p>Automatic status checks have ended.</p>}
                <button type="button" onClick={refreshStatus} className="mt-2 underline">Refresh status</button>
              </div>}
              <div>
                <label htmlFor="welcome-phone" className="block text-sm font-medium text-gray-700 mb-1">Patient mobile number</label>
                <input id="welcome-phone" type="tel" autoComplete="off" value={singlePhone}
                  onChange={event => resetRecipient(event.target.value)} disabled={isSendingSingle}
                  placeholder="10-digit Indian number or +country code"
                  className="w-full border border-gray-300 rounded-lg px-4 py-2" required />
              </div>
              <div>
                <label htmlFor="welcome-language" className="block text-sm font-medium text-gray-700 mb-1">Message language</label>
                <select id="welcome-language" value={language} disabled={isSendingSingle}
                  onChange={event => { resetRecipient(singlePhone, event.target.value as Language); }}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2">
                  <option value="en">English</option><option value="ml">Malayalam / മലയാളം</option>
                </select>
              </div>
              {config?.templates[language] && <div className="text-sm bg-gray-50 p-3 rounded-lg">
                <p className="font-medium mb-2">Message preview</p>
                <p className="whitespace-pre-wrap">{config.templates[language]?.preview}</p>
              </div>}
              <label className="flex gap-2 items-start text-sm text-gray-700">
                <input type="checkbox" checked={permission} disabled={isSendingSingle}
                  onChange={event => setPermission(event.target.checked)} className="mt-1" />
                <span>The patient agreed to receive this WhatsApp welcome from Arogya for this hospital.</span>
              </label>
              <button type="submit" disabled={isSendingSingle || !config?.enabled || !config.templates[language] || !singlePhone.trim() || !permission || message?.status === 'pending' || message?.status === 'unknown'}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50">
                {isSendingSingle ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                {isSendingSingle ? 'Submitting…' : 'Send welcome'}
              </button>
            </form>
          </div>
        </section>

        {/* Bulk Upload Form */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-100 bg-gray-50 px-6 py-4">
            <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-gray-500" /> Legacy bulk send via Twilio
            </h2>
          </div>
          
          <div className="p-6">
            <form onSubmit={handleBulkUpload} className="space-y-4">
              {bulkStatus && (
                <div className={`p-4 rounded-lg flex flex-col gap-2 text-sm ${
                  bulkStatus.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                }`}>
                  <div className="flex gap-3">
                    {bulkStatus.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
                    <span className="font-semibold">{bulkStatus.msg}</span>
                  </div>
                  {bulkStatus.details && (
                    <div className="ml-8 mt-2 space-y-1">
                      <p>Successfully Sent: <span className="font-bold text-green-700">{bulkStatus.details.sent}</span></p>
                      <p>Failed: <span className="font-bold text-red-700">{bulkStatus.details.failed}</span></p>
                      {bulkStatus.details.errors.length > 0 && (
                        <div className="mt-2 text-xs bg-white bg-opacity-50 p-2 rounded max-h-32 overflow-auto">
                          {bulkStatus.details.errors.map((err, i) => (
                            <p key={i} className="text-red-600">{err}</p>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Excel File</label>
                <p className="text-xs text-gray-500 mb-2">Must contain a column named <b>Phone</b>. Other columns can be used as variables.</p>
                <label className="flex items-center justify-center w-full p-4 border-2 border-dashed border-gray-300 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
                  <input 
                    type="file" 
                    accept=".xlsx, .xls"
                    className="hidden" 
                    onChange={e => setBulkFile(e.target.files?.[0] || null)}
                  />
                  <div className="flex flex-col items-center">
                    <Upload className="w-6 h-6 text-gray-400 mb-2" />
                    <span className="text-sm text-gray-600">
                      {bulkFile ? bulkFile.name : 'Click to select Excel file'}
                    </span>
                  </div>
                </label>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Message Template</label>
                <p className="text-xs text-gray-500 mb-2">Use curly braces for variables matching Excel columns (e.g. <code className="bg-gray-100 px-1 rounded">Hello &#123;Name&#125;</code>)</p>
                <textarea 
                  value={bulkTemplate}
                  onChange={e => setBulkTemplate(e.target.value)}
                  placeholder="Hello {Name}, your appointment is on {Date}..."
                  rows={4}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none resize-none"
                  required
                />
              </div>
              
              <button 
                type="submit" 
                disabled={isSendingBulk || !bulkFile || !bulkTemplate}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSendingBulk ? <Loader2 className="w-5 h-5 animate-spin" /> : <FileSpreadsheet className="w-5 h-5" />}
                {isSendingBulk ? 'Processing...' : 'Send Bulk Messages'}
              </button>
            </form>
          </div>
        </div>

      </div>
    </div>
  );
}

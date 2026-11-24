import { useEffect, useRef, useState, type FormEvent } from 'react';
import { isAxiosError } from 'axios';
import api from '../api/axios';

type Language = 'en' | 'ml';
type ImportedRow = {
  name: string;
  original_phone: string;
  phone: string;
  source: string;
  issue: string | null;
};
type Row = ImportedRow & { reviewed: boolean; consent: boolean; language: Language };
type Batch = {
  batch_id: string;
  items: { position: number; masked_phone: string; status: string; error_code: string | null }[];
};

const errors: Record<string, string> = {
  sheet_headers: 'Use a Phone or Mobile column and an optional Name column.',
  one_sheet_required: 'Upload an Excel workbook with one worksheet.',
  too_many_columns: 'The worksheet must have 64 columns or fewer.',
  too_many_rows: 'The file must contain 100 recipient rows or fewer.',
  too_many_pages: 'Upload a document with five pages or fewer.',
  page_too_large: 'Resize the image or PDF page and upload it again.',
  file_too_large: 'Upload a smaller file. The upload limit is 5 MB.',
  no_recipients: 'No recipient rows were found. Try a clearer image or export a spreadsheet.',
  ocr_unavailable: 'Photo and scanned PDF extraction is unavailable. Ask your administrator to configure OCR.',
  import_busy: 'Another file is being scanned. Try again in a moment.',
  import_timeout: 'Scanning took too long. Try fewer pages or a smaller image.',
  permission_required: 'Confirm review and WhatsApp permission for every included row.',
  duplicate_recipients: 'The batch contains duplicate numbers. Include each number once.',
  invalid_phone: 'A selected number is invalid. Check the digits and country code.',
  recipient_already_in_progress: 'At least one number has a pending or uncertain batch send. Check the previous batch. Do not send again to an uncertain number.',
  setup_required: 'WhatsApp sending is unavailable for this hospital.',
  batch_setup_required: 'Batch sending is unavailable. Ask your administrator to check setup.',
  hospital_unavailable: 'This hospital is unavailable.',
  request_conflict: 'This approval ID is already in use. Check its status before starting another batch.',
};

function errorCode(error: unknown): string | undefined {
  return isAxiosError(error) ? error.response?.data?.detail?.code : undefined;
}

function readTicket(key: string) {
  try { return sessionStorage.getItem(key); } catch { return null; }
}

function writeTicket(key: string, ticket: string | null) {
  try {
    if (ticket) sessionStorage.setItem(key, ticket);
    else sessionStorage.removeItem(key);
  } catch { /* Batch status remains available in this view. */ }
}

export default function WelcomeBatch({ hospitalId, enabled, templates }: {
  hospitalId: string;
  enabled: boolean;
  templates: Partial<Record<Language, { preview: string }>>;
}) {
  const path = '/hospitals/' + hospitalId + '/whatsapp';
  const ticketKey = 'arogya:welcome-batch:' + hospitalId;
  const [rows, setRows] = useState<Row[]>([]);
  const [batchId, setBatchId] = useState<string | null>(() => readTicket(ticketKey));
  const [batch, setBatch] = useState<Batch | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  const [refreshCount, setRefreshCount] = useState(0);
  const inFlight = useRef(false);

  useEffect(() => {
    if (!batchId) return;
    const controller = new AbortController();
    let timer: number;
    const expires = Date.now() + 65 * 60_000;
    const refresh = async () => {
      try {
        const { data } = await api.get<Batch>(path + '/welcome-batches/' + batchId, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setBatch(data);
        setMissing(false);
        setRows([]);
        setNotice(null);
      } catch (error: unknown) {
        if (controller.signal.aborted) return;
        if (errorCode(error) === 'batch_not_found') setMissing(true);
      }
      if (Date.now() < expires) timer = window.setTimeout(refresh, 5000);
    };
    void refresh();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [batchId, path, refreshCount]);

  const importFile = async (file: File) => {
    const extension = file.name.split('.').pop()?.toLowerCase();
    const kind = extension === 'jpg' ? 'jpeg' : extension;
    if (!kind || !['xlsx', 'csv', 'pdf', 'png', 'jpeg'].includes(kind)) {
      setNotice('Choose a .xlsx, .csv, .pdf, .jpg, or .png file.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setNotice(errors.file_too_large);
      return;
    }
    setBusy(true);
    setRows([]);
    setNotice(null);
    try {
      const { data } = await api.post<{ rows: ImportedRow[] }>(path + '/welcome-import/' + kind, file, {
        headers: { 'Content-Type': 'application/octet-stream' },
      });
      setRows(data.rows.map(row => ({ ...row, reviewed: false, consent: false, language: 'en' })));
    } catch (error: unknown) {
      setNotice(errors[errorCode(error) ?? ''] ?? 'Could not read the file. Check the format or try a clearer copy.');
    } finally { setBusy(false); }
  };

  const update = (index: number, change: Partial<Row>) => {
    setRows(previous => previous.map((row, i) => i === index ? { ...row, ...change } : row));
  };

  const selected = rows.filter(row => row.reviewed && row.consent);
  const duplicate = new Set(selected.map(row => row.phone.trim())).size !== selected.length;
  const canApprove = enabled && selected.length > 0 && !duplicate
    && selected.every(row => Boolean(row.phone.trim() && templates[row.language]));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!canApprove || inFlight.current || batch) return;
    inFlight.current = true;
    setBusy(true);
    setNotice(null);
    const ticket = batchId ?? crypto.randomUUID();
    writeTicket(ticketKey, ticket);
    try {
      const { data } = await api.post<Batch>(path + '/welcome-batches/' + ticket, {
        recipients: selected.map(row => ({
          phone: row.phone.trim(), language: row.language,
          reviewed: row.reviewed, consent_confirmed: row.consent,
        })),
      });
      setBatch(data);
      setBatchId(ticket);
      setRows([]);
    } catch (error: unknown) {
      const code = errorCode(error);
      if (code && code in errors && code !== 'request_conflict') {
        setNotice(errors[code]);
        setBatchId(null);
        writeTicket(ticketKey, null);
      } else {
        setBatchId(ticket);
        setNotice('Could not confirm approval. Check the batch status or retry the same approval.');
      }
    } finally { inFlight.current = false; setBusy(false); }
  };

  const startOver = () => {
    setBatch(null);
    setBatchId(null);
    setMissing(false);
    setRows([]);
    setNotice(null);
    writeTicket(ticketKey, null);
  };

  if (!enabled && !batchId) return null;

  return (
    <section className="space-y-4 rounded-xl border border-gray-200 bg-white p-6">
      <h2 className="text-lg font-bold text-gray-800">Upload patient list</h2>
      {notice && <p role="alert" className="text-sm text-red-700">{notice}</p>}
      {!batchId && (
        <label className="block space-y-2 text-sm">
          <span>Excel (.xlsx), CSV, PDF, JPG, or PNG. Up to 100 rows, five pages, and 5 MB.</span>
          <input className="block" type="file" accept=".xlsx,.csv,.pdf,.png,.jpg,.jpeg" disabled={busy}
            onChange={event => {
              const file = event.target.files?.[0];
              event.target.value = '';
              if (file) void importFile(file);
            }} />
        </label>
      )}
      {busy && <p role="status">{rows.length ? 'Submitting approval…' : 'Scanning file…'}</p>}
      {rows.length > 0 && (
        <form onSubmit={submit} className="space-y-4">
          <p className="text-sm">Compare each name and number with the source and confirm permission. Only rows with both boxes checked will be sent.</p>
          {duplicate && <p role="alert" className="text-sm text-red-700">Select each number only once.</p>}
          <fieldset disabled={busy || !!batchId}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead><tr>
                  <th scope="col">Source</th><th scope="col">Name</th><th scope="col">Extracted number</th>
                  <th scope="col">Number to send to</th><th scope="col">Language</th>
                  <th scope="col">Review</th><th scope="col">Permission</th>
                </tr></thead>
                <tbody>
                  {rows.map((row, index) => (
                    <tr key={index} className="border-t border-gray-200">
                      <td className="p-2">{row.source}{row.issue && <p className="text-amber-800">{row.issue}</p>}</td>
                      <td className="p-2"><input className="w-36 rounded border p-1" aria-label={'Name, row ' + (index + 1)}
                        value={row.name} maxLength={120} onChange={event => update(index, { name: event.target.value, reviewed: false, consent: false })} /></td>
                      <td className="p-2">{row.original_phone || 'None found'}</td>
                      <td className="p-2"><input className="w-40 rounded border p-1" type="tel" autoComplete="off"
                        aria-label={'Phone, row ' + (index + 1)} value={row.phone} maxLength={40}
                        onChange={event => update(index, { phone: event.target.value, reviewed: false, consent: false })} /></td>
                      <td className="p-2"><select className="rounded border p-1" aria-label={'Language, row ' + (index + 1)}
                        value={row.language} onChange={event => update(index, { language: event.target.value === 'ml' ? 'ml' : 'en', consent: false })}>
                        <option value="en">English</option><option value="ml">Malayalam</option>
                      </select></td>
                      <td className="p-2"><label className="flex items-center gap-2">
                        <input type="checkbox" aria-label={'Verified name and number, row ' + (index + 1)} checked={row.reviewed}
                          onChange={event => update(index, { reviewed: event.target.checked, consent: false })} /> Verified
                      </label></td>
                      <td className="p-2"><label className="flex items-center gap-2">
                        <input type="checkbox" aria-label={'Patient opted in, row ' + (index + 1)} checked={row.consent}
                          disabled={!row.reviewed} onChange={event => update(index, { consent: event.target.checked })} /> Opted in
                      </label></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </fieldset>
          {(['en', 'ml'] as const).filter(language => selected.some(row => row.language === language)).map(language => (
            <details key={language} className="rounded-lg bg-gray-50 p-3 text-sm">
              <summary>{language === 'en' ? 'English' : 'Malayalam'} message preview</summary>
              <p className="whitespace-pre-wrap">{templates[language]?.preview ?? 'Template unavailable'}</p>
            </details>
          ))}
          <button type="submit" disabled={busy || !canApprove} className="rounded-lg bg-blue-600 px-4 py-2 text-white disabled:opacity-50">
            {batchId ? 'Retry same approval' : 'Approve and send (' + selected.length + ')'}
          </button>
        </form>
      )}
      {batchId && !batch && rows.length === 0 && (
        <p role="status">{missing ? 'No approved batch was found for this account. Check the account before uploading again.' : 'Checking batch status…'}</p>
      )}
      {batch && (
        <div className="space-y-2" aria-live="polite">
          <h3 className="font-medium">Batch status</h3>
          <ul className="text-sm">
            {batch.items.map(item => (
              <li key={item.position}>{item.masked_phone} — {item.status}
                {item.status === 'unknown' && ' · Do not send again to this number.'}
                {item.error_code && <span> ({item.error_code})</span>}
              </li>
            ))}
          </ul>
          <button type="button" className="text-sm text-blue-700 underline" onClick={() => setRefreshCount(count => count + 1)}>
            Refresh batch status
          </button>
        </div>
      )}
      {batchId && (batch || (missing && rows.length === 0)) && (
        <button type="button" className="text-sm text-blue-700 underline" onClick={startOver}>Start a new upload</button>
      )}
    </section>
  );
}

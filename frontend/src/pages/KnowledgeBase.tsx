import React, { useState } from 'react';
import api from '../api/axios';
import { FileText, Send, Upload, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

interface UploadResult {
  filename: string;
  pages_processed: number;
  chunks_stored: number;
  total_characters: number;
  message: string;
}

const KnowledgeBaseUpload = ({ hospitalId }: { hospitalId: string | undefined }) => {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploadType, setUploadType] = useState<'text' | 'pdf'>('text');

  // Replaced alert() with inline status so the user gets real feedback
  // without a browser dialog that blocks the UI and shows no detail.
  const [status, setStatus] = useState<{
    type: 'success' | 'error';
    message: string;
    detail?: UploadResult;
  } | null>(null);

  const clearStatus = () => setStatus(null);

  // ── TEXT UPLOAD ────────────────────────────────────────────────────────────

  const handleTextUpload = async () => {
    if (!hospitalId) {
      setStatus({ type: 'error', message: 'No hospital selected.' });
      return;
    }
    if (!text.trim()) {
      setStatus({ type: 'error', message: 'Please enter some text before uploading.' });
      return;
    }

    setLoading(true);
    clearStatus();

    try {
      await api.post('/ai/ingest', {
        text: text.trim(),
        hospital_id: Number(hospitalId),
      });
      setStatus({ type: 'success', message: 'Knowledge synced to Arogya\'s brain successfully.' });
      setText('');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setStatus({
        type: 'error',
        message: typeof detail === 'string'
          ? detail
          : 'Failed to upload knowledge. Please try again.',
      });
    } finally {
      setLoading(false);
    }
  };

  // ── PDF UPLOAD ─────────────────────────────────────────────────────────────

  const handlePdfUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !hospitalId) return;

    // Client-side type check before hitting the network
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setStatus({ type: 'error', message: 'Only PDF files are accepted.' });
      event.target.value = '';
      return;
    }

    setLoading(true);
    clearStatus();

    // hospital_id must be a FormData field (not JSON body) because this is
    // a multipart request. The backend declares it as Form(...) and coerces
    // the string to int automatically.
    const formData = new FormData();
    formData.append('file', file);
    formData.append('hospital_id', hospitalId);

    try {
      const response = await api.post('/ai/upload-pdf', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      // Backend returns a structured result — show it to the admin
      const result: UploadResult = response.data;
      setStatus({
        type: 'success',
        message: result.message,
        detail: result,
      });
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setStatus({
        type: 'error',
        message: typeof detail === 'string'
          ? detail
          : 'Failed to process PDF. The file may be scanned, password-protected, or corrupted.',
      });
    } finally {
      setLoading(false);
      // Reset the file input so the same file can be re-uploaded if needed
      event.target.value = '';
    }
  };

  // ── RENDER ─────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-4xl bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      {/* Tab switcher */}
      <div className="flex border-b border-gray-100">
        <button
          onClick={() => { setUploadType('text'); clearStatus(); }}
          className={`flex-1 p-4 text-sm font-medium flex items-center justify-center gap-2 transition-colors ${
            uploadType === 'text'
              ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50/30'
              : 'text-gray-500 hover:bg-gray-50'
          }`}
        >
          <Send className="w-4 h-4" /> Manual Text
        </button>
        <button
          onClick={() => { setUploadType('pdf'); clearStatus(); }}
          className={`flex-1 p-4 text-sm font-medium flex items-center justify-center gap-2 transition-colors ${
            uploadType === 'pdf'
              ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50/30'
              : 'text-gray-500 hover:bg-gray-50'
          }`}
        >
          <FileText className="w-4 h-4" /> Upload PDF
        </button>
      </div>

      <div className="p-8">

        {/* Inline status banner — replaces all alert() calls */}
        {status && (
          <div className={`mb-6 p-4 rounded-xl flex gap-3 items-start border ${
            status.type === 'success'
              ? 'bg-green-50 border-green-100 text-green-800'
              : 'bg-red-50 border-red-100 text-red-800'
          }`}>
            {status.type === 'success'
              ? <CheckCircle className="w-5 h-5 mt-0.5 shrink-0 text-green-600" />
              : <AlertCircle className="w-5 h-5 mt-0.5 shrink-0 text-red-600" />
            }
            <div className="flex-1">
              <p className="text-sm font-medium">{status.message}</p>

              {/* PDF upload success shows the chunk breakdown */}
              {status.type === 'success' && status.detail && (
                <div className="mt-3 grid grid-cols-3 gap-3">
                  <div className="bg-white rounded-lg p-3 border border-green-100 text-center">
                    <p className="text-xl font-bold text-green-700">
                      {status.detail.pages_processed}
                    </p>
                    <p className="text-xs text-green-600 mt-0.5">Pages read</p>
                  </div>
                  <div className="bg-white rounded-lg p-3 border border-green-100 text-center">
                    <p className="text-xl font-bold text-green-700">
                      {status.detail.chunks_stored}
                    </p>
                    <p className="text-xs text-green-600 mt-0.5">Chunks stored</p>
                  </div>
                  <div className="bg-white rounded-lg p-3 border border-green-100 text-center">
                    <p className="text-xl font-bold text-green-700">
                      {status.detail.total_characters.toLocaleString()}
                    </p>
                    <p className="text-xs text-green-600 mt-0.5">Characters ingested</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Text upload panel */}
        {uploadType === 'text' && (
          <div className="space-y-4">
            <h3 className="text-lg font-bold text-gray-800">Train with Text</h3>
            <p className="text-sm text-gray-500">
              Paste FAQs, rules, or any hospital information for Arogya to learn.
            </p>
            <textarea
              className="w-full h-48 p-4 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-sm leading-relaxed resize-none"
              placeholder="Enter knowledge here — e.g. 'The OPD is open Monday to Saturday, 8am to 6pm. Emergency is open 24 hours.'"
              value={text}
              onChange={e => setText(e.target.value)}
              disabled={loading}
            />
            <button
              onClick={handleTextUpload}
              disabled={loading || !text.trim()}
              className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-300 font-semibold transition-colors flex items-center justify-center gap-2"
            >
              {loading
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Syncing...</>
                : 'Sync to AI Brain'
              }
            </button>
          </div>
        )}

        {/* PDF upload panel */}
        {uploadType === 'pdf' && (
          <div className="space-y-4">
            <h3 className="text-lg font-bold text-gray-800">Upload Hospital PDF</h3>
            <p className="text-sm text-gray-500">
              Brochures, staff directories, policy documents — Arogya will read and
              index every page automatically. PDF must contain selectable text (not scanned images).
            </p>

            <div className={`py-12 text-center border-2 border-dashed rounded-xl transition-colors ${
              loading ? 'border-blue-200 bg-blue-50/30' : 'border-gray-200 bg-gray-50/50 hover:border-blue-300'
            }`}>
              {loading ? (
                <div className="flex flex-col items-center gap-3">
                  <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
                  <p className="text-sm font-medium text-blue-600">
                    Reading and indexing PDF...
                  </p>
                  <p className="text-xs text-gray-400">
                    This may take a few seconds for large documents
                  </p>
                </div>
              ) : (
                <>
                  <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Upload className="w-8 h-8 text-blue-600" />
                  </div>
                  <p className="text-sm text-gray-600 mb-1 font-medium">
                    Drop a PDF or click to select
                  </p>
                  <p className="text-xs text-gray-400 mb-4">
                    Max recommended size: 10MB
                  </p>
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={handlePdfUpload}
                    id="pdf-input"
                    className="hidden"
                    disabled={loading}
                  />
                  <label
                    htmlFor="pdf-input"
                    className="cursor-pointer px-8 py-3 bg-white border border-blue-600 text-blue-600 rounded-lg hover:bg-blue-50 font-medium transition-all inline-block"
                  >
                    Select PDF
                  </label>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default KnowledgeBaseUpload;
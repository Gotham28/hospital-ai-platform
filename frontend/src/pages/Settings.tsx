import React, { useState, useEffect, useCallback } from 'react';
import api from '../api/axios';
import {
  FileText, Send, Upload, CheckCircle, AlertCircle, Loader2,
  Trash2, Pencil, X, Check, BookOpen, Lightbulb, RefreshCw
} from 'lucide-react';

interface UploadResult {
  filename: string;
  pages_processed: number;
  chunks_stored: number;
  total_characters: number;
  message: string;
}

interface KnowledgeEntry {
  id: number;
  content: string;
  entry_type: 'instruction' | 'fact';
  created_at: string;
}

const ENTRY_TYPE_OPTIONS = [
  {
    value: 'fact' as const,
    label: 'Fact / Rule',
    icon: BookOpen,
    description: 'Hospital info, schedules, policies, FAQs',
    color: 'blue',
  },
  {
    value: 'instruction' as const,
    label: 'Instruction',
    icon: Lightbulb,
    description: 'How the AI should behave or respond',
    color: 'purple',
  },
];

const KnowledgeBaseUpload = ({ hospitalId }: { hospitalId: string | undefined }) => {
  const [text, setText] = useState('');
  const [entryType, setEntryType] = useState<'fact' | 'instruction'>('fact');
  const [loading, setLoading] = useState(false);
  const [uploadType, setUploadType] = useState<'text' | 'pdf'>('text');

  const [status, setStatus] = useState<{
    type: 'success' | 'error';
    message: string;
    detail?: UploadResult;
  } | null>(null);

  // --- Knowledge entries list ---
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(false);
  const [entriesError, setEntriesError] = useState<string | null>(null);

  // --- Edit state ---
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editContent, setEditContent] = useState('');
  const [editSaving, setEditSaving] = useState(false);

  // --- Delete state ---
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const clearStatus = () => setStatus(null);

  // ── FETCH ENTRIES ────────────────────────────────────────────────────────────
  const fetchEntries = useCallback(async () => {
    if (!hospitalId) return;
    setEntriesLoading(true);
    setEntriesError(null);
    try {
      const res = await api.get(`/ai/knowledge/${hospitalId}`);
      setEntries(res.data || []);
    } catch {
      setEntriesError('Failed to load knowledge entries.');
    } finally {
      setEntriesLoading(false);
    }
  }, [hospitalId]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

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
        entry_type: entryType,
      });
      setStatus({ type: 'success', message: 'Knowledge synced to Arogya\'s brain successfully.' });
      setText('');
      fetchEntries(); // Refresh the list
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

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setStatus({ type: 'error', message: 'Only PDF files are accepted.' });
      event.target.value = '';
      return;
    }

    setLoading(true);
    clearStatus();

    const formData = new FormData();
    formData.append('file', file);
    formData.append('hospital_id', hospitalId);
    formData.append('entry_type', entryType);

    try {
      const response = await api.post('/ai/upload-pdf', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const result: UploadResult = response.data;
      setStatus({ type: 'success', message: result.message, detail: result });
      fetchEntries();
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
      event.target.value = '';
    }
  };

  // ── DELETE ─────────────────────────────────────────────────────────────────
  const handleDelete = async (id: number) => {
    setDeletingId(id);
    try {
      await api.delete(`/ai/knowledge/entry/${id}`);
      setEntries(prev => prev.filter(e => e.id !== id));
    } catch {
      alert('Failed to delete entry. Please try again.');
    } finally {
      setDeletingId(null);
    }
  };

  // ── EDIT ───────────────────────────────────────────────────────────────────
  const startEdit = (entry: KnowledgeEntry) => {
    setEditingId(entry.id);
    setEditContent(entry.content);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditContent('');
  };

  const saveEdit = async (id: number) => {
    if (!editContent.trim()) return;
    setEditSaving(true);
    try {
      await api.patch(`/ai/knowledge/entry/${id}`, { content: editContent.trim() });
      setEntries(prev => prev.map(e => e.id === id ? { ...e, content: editContent.trim() } : e));
      setEditingId(null);
    } catch {
      alert('Failed to save changes. Please try again.');
    } finally {
      setEditSaving(false);
    }
  };

  // ── RENDER ─────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-4xl space-y-6">

      {/* ── Upload card ─────────────────────────────────────────────────────── */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
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

          {/* Entry type selector */}
          <div className="mb-6">
            <p className="text-sm font-medium text-gray-700 mb-3">Entry Type</p>
            <div className="grid grid-cols-2 gap-3">
              {ENTRY_TYPE_OPTIONS.map(opt => {
                const Icon = opt.icon;
                const isSelected = entryType === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setEntryType(opt.value)}
                    className={`flex items-start gap-3 p-4 rounded-xl border-2 text-left transition-all ${
                      isSelected
                        ? opt.color === 'blue'
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-purple-500 bg-purple-50'
                        : 'border-gray-200 hover:border-gray-300 bg-white'
                    }`}
                  >
                    <Icon className={`w-5 h-5 mt-0.5 shrink-0 ${
                      isSelected
                        ? opt.color === 'blue' ? 'text-blue-600' : 'text-purple-600'
                        : 'text-gray-400'
                    }`} />
                    <div>
                      <p className={`text-sm font-semibold ${
                        isSelected
                          ? opt.color === 'blue' ? 'text-blue-700' : 'text-purple-700'
                          : 'text-gray-700'
                      }`}>{opt.label}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{opt.description}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Inline status banner */}
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
                {status.type === 'success' && status.detail && (
                  <div className="mt-3 grid grid-cols-3 gap-3">
                    <div className="bg-white rounded-lg p-3 border border-green-100 text-center">
                      <p className="text-xl font-bold text-green-700">{status.detail.pages_processed}</p>
                      <p className="text-xs text-green-600 mt-0.5">Pages read</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border border-green-100 text-center">
                      <p className="text-xl font-bold text-green-700">{status.detail.chunks_stored}</p>
                      <p className="text-xs text-green-600 mt-0.5">Chunks stored</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border border-green-100 text-center">
                      <p className="text-xl font-bold text-green-700">{status.detail.total_characters.toLocaleString()}</p>
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
              <div>
                <h3 className="text-lg font-bold text-gray-800">Train with Text</h3>
                <p className="text-sm text-gray-500 mt-1">
                  {entryType === 'fact'
                    ? 'Paste FAQs, schedules, policies, or any hospital information for Arogya to learn.'
                    : 'Enter instructions for how Arogya should behave — tone, rules, what to avoid, etc.'}
                </p>
              </div>
              <textarea
                className="w-full h-48 p-4 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-sm leading-relaxed resize-none"
                placeholder={entryType === 'fact'
                  ? "e.g. 'The OPD is open Monday to Saturday, 8am to 6pm. Emergency is open 24 hours.'"
                  : "e.g. 'Always recommend calling reception for billing questions. Never share doctor personal numbers.'"}
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
              <div>
                <h3 className="text-lg font-bold text-gray-800">Upload Hospital PDF</h3>
                <p className="text-sm text-gray-500 mt-1">
                  Brochures, staff directories, policy documents — Arogya will read and
                  index every page automatically. PDF must contain selectable text (not scanned images).
                </p>
              </div>

              <div className={`py-12 text-center border-2 border-dashed rounded-xl transition-colors ${
                loading ? 'border-blue-200 bg-blue-50/30' : 'border-gray-200 bg-gray-50/50 hover:border-blue-300'
              }`}>
                {loading ? (
                  <div className="flex flex-col items-center gap-3">
                    <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
                    <p className="text-sm font-medium text-blue-600">Reading and indexing PDF...</p>
                    <p className="text-xs text-gray-400">This may take a few seconds for large documents</p>
                  </div>
                ) : (
                  <>
                    <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                      <Upload className="w-8 h-8 text-blue-600" />
                    </div>
                    <p className="text-sm text-gray-600 mb-1 font-medium">Drop a PDF or click to select</p>
                    <p className="text-xs text-gray-400 mb-4">Max recommended size: 10MB</p>
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

      {/* ── Knowledge entries list ───────────────────────────────────────────── */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="border-b border-gray-100 px-6 py-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-gray-900">Stored Knowledge</h3>
            <p className="text-xs text-gray-500 mt-0.5">All information Arogya has learned for this hospital</p>
          </div>
          <button
            onClick={fetchEntries}
            disabled={entriesLoading}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-blue-600 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${entriesLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {entriesLoading && (
          <div className="flex items-center justify-center py-12 gap-2 text-gray-400">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">Loading entries...</span>
          </div>
        )}

        {entriesError && !entriesLoading && (
          <div className="flex items-center gap-2 m-6 p-3 bg-red-50 text-red-700 rounded-lg text-sm border border-red-100">
            <AlertCircle className="w-4 h-4 shrink-0" /> {entriesError}
          </div>
        )}

        {!entriesLoading && !entriesError && entries.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <BookOpen className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="text-sm font-medium">No knowledge entries yet</p>
            <p className="text-xs mt-1">Add text or upload a PDF above to get started.</p>
          </div>
        )}

        {!entriesLoading && entries.length > 0 && (
          <ul className="divide-y divide-gray-50">
            {entries.map(entry => {
              const isEditing = editingId === entry.id;
              const isDeleting = deletingId === entry.id;
              const typeOpt = ENTRY_TYPE_OPTIONS.find(o => o.value === entry.entry_type) ?? ENTRY_TYPE_OPTIONS[0];
              const TypeIcon = typeOpt.icon;

              return (
                <li key={entry.id} className="px-6 py-4 hover:bg-gray-50/50 transition-colors">
                  <div className="flex items-start gap-3">
                    {/* Type badge */}
                    <span className={`mt-0.5 shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${
                      entry.entry_type === 'instruction'
                        ? 'bg-purple-100 text-purple-700'
                        : 'bg-blue-100 text-blue-700'
                    }`}>
                      <TypeIcon className="w-2.5 h-2.5" />
                      {typeOpt.label}
                    </span>

                    {/* Content / edit area */}
                    <div className="flex-1 min-w-0">
                      {isEditing ? (
                        <textarea
                          className="w-full p-2 text-sm border border-blue-300 rounded-lg focus:ring-2 focus:ring-blue-400 outline-none resize-none leading-relaxed"
                          rows={Math.min(8, editContent.split('\n').length + 2)}
                          value={editContent}
                          onChange={e => setEditContent(e.target.value)}
                          autoFocus
                        />
                      ) : (
                        <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap break-words">
                          {entry.content}
                        </p>
                      )}
                      <p className="text-[11px] text-gray-400 mt-1.5">
                        Added {new Date(entry.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                      </p>
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-1 shrink-0">
                      {isEditing ? (
                        <>
                          <button
                            onClick={() => saveEdit(entry.id)}
                            disabled={editSaving || !editContent.trim()}
                            className="p-1.5 rounded-lg text-green-600 hover:bg-green-50 disabled:opacity-40 transition-colors"
                            title="Save"
                          >
                            {editSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                          </button>
                          <button
                            onClick={cancelEdit}
                            disabled={editSaving}
                            className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100 transition-colors"
                            title="Cancel"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => startEdit(entry)}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                            title="Edit"
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(entry.id)}
                            disabled={isDeleting}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 disabled:opacity-40 transition-colors"
                            title="Delete"
                          >
                            {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
};

export default KnowledgeBaseUpload;
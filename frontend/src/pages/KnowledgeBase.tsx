import React, { useState } from 'react';
import api from '../api/axios';
import { FileText, Send, Upload } from 'lucide-react';

// Added hospitalId prop to the component definition
const KnowledgeBaseUpload = ({ hospitalId }: { hospitalId: string | undefined }) => {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploadType, setUploadType] = useState<'text' | 'pdf'>('text');

  const handleTextUpload = async () => {
    if (!hospitalId) return alert("No hospital selected");
    setLoading(true);
    try {
      // Include hospital_id in the payload
      await api.post('/ai/ingest', { 
        text: text,
        hospital_id: hospitalId 
      });
      alert("Arogya has learned this information!");
      setText('');
    } catch (err) {
      alert("Failed to upload knowledge.");
    } finally {
      setLoading(false);
    }
  };

  const handlePdfUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !hospitalId) return;

    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);
    // Explicitly append hospital_id to formData for the multi-part request
    formData.append('hospital_id', hospitalId);

    try {
      await api.post('/ai/upload-pdf', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      alert(`${file.name} has been processed and added to Arogya's brain!`);
    } catch (err) {
      alert("Failed to process PDF.");
    } finally {
      setLoading(false);
      event.target.value = ''; 
    }
  };

  return (
    <div className="max-w-4xl bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div className="flex border-b border-gray-100">
        <button 
          onClick={() => setUploadType('text')}
          className={`flex-1 p-4 text-sm font-medium flex items-center justify-center gap-2 ${uploadType === 'text' ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50/30' : 'text-gray-500 hover:bg-gray-50'}`}
        >
          <Send className="w-4 h-4" /> Manual Text
        </button>
        <button 
          onClick={() => setUploadType('pdf')}
          className={`flex-1 p-4 text-sm font-medium flex items-center justify-center gap-2 ${uploadType === 'pdf' ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50/30' : 'text-gray-500 hover:bg-gray-50'}`}
        >
          <FileText className="w-4 h-4" /> Upload PDF
        </button>
      </div>

      <div className="p-8">
        {uploadType === 'text' && (
          <div className="space-y-4">
            <h3 className="text-lg font-bold text-gray-800">Train with Text</h3>
            <p className="text-sm text-gray-500">Paste FAQs or rules for this specific hospital.</p>
            <textarea 
              className="w-full h-48 p-4 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none text-sm leading-relaxed"
              placeholder="Enter knowledge here..."
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <button 
              onClick={handleTextUpload}
              disabled={loading || !text}
              className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-300 font-semibold transition-colors flex items-center justify-center gap-2"
            >
              {loading ? 'Processing...' : 'Sync to AI Brain'}
            </button>
          </div>
        )}

        {uploadType === 'pdf' && (
          <div className="py-12 text-center border-2 border-dashed border-gray-200 rounded-xl bg-gray-50/50">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Upload className="w-8 h-8 text-blue-600" />
            </div>
            <h3 className="text-lg font-bold text-gray-800">Drop Hospital PDF here</h3>
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
              className={`cursor-pointer px-8 py-3 bg-white border border-blue-600 text-blue-600 rounded-lg hover:bg-blue-50 font-medium transition-all ${loading ? 'opacity-50 pointer-events-none' : ''}`}
            >
              {loading ? 'Reading Document...' : 'Select File'}
            </label>
          </div>
        )}
      </div>
    </div>
  );
};

export default KnowledgeBaseUpload;
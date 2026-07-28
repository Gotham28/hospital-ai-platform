import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { MessageSquare, Send, Upload, FileSpreadsheet, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import api from '../api/axios';

export default function MessagingPage() {
  const { hospitalId } = useParams();
  
  // Single Message State
  const [singlePhone, setSinglePhone] = useState('');
  const [singleMessage, setSingleMessage] = useState('');
  const [isSendingSingle, setIsSendingSingle] = useState(false);
  const [singleStatus, setSingleStatus] = useState<{type: 'success' | 'error', msg: string} | null>(null);

  // Bulk Message State
  const [bulkFile, setBulkFile] = useState<File | null>(null);
  const [bulkTemplate, setBulkTemplate] = useState('');
  const [isSendingBulk, setIsSendingBulk] = useState(false);
  const [bulkStatus, setBulkStatus] = useState<{
    type: 'success' | 'error';
    msg: string;
    details?: { sent: number; failed: number; errors: string[] };
  } | null>(null);

  const handleSendSingle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!singlePhone || !singleMessage) return;
    
    setIsSendingSingle(true);
    setSingleStatus(null);
    try {
      await api.post(`/hospitals/${hospitalId}/whatsapp/send-single`, {
        phone: singlePhone,
        message: singleMessage
      });
      setSingleStatus({ type: 'success', msg: 'Message sent successfully!' });
      setSinglePhone('');
      setSingleMessage('');
    } catch (err: any) {
      setSingleStatus({ 
        type: 'error', 
        msg: err.response?.data?.detail || 'Failed to send message' 
      });
    } finally {
      setIsSendingSingle(false);
    }
  };

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
    } catch (err: any) {
      setBulkStatus({ 
        type: 'error', 
        msg: err.response?.data?.detail || 'Failed to process bulk upload' 
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
        
        {/* Single Message Form */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-100 bg-gray-50 px-6 py-4">
            <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
              <Send className="w-5 h-5 text-gray-500" /> Send Single Message
            </h2>
          </div>
          
          <div className="p-6">
            <form onSubmit={handleSendSingle} className="space-y-4">
              {singleStatus && (
                <div className={`p-4 rounded-lg flex gap-3 text-sm ${
                  singleStatus.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                }`}>
                  {singleStatus.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
                  {singleStatus.msg}
                </div>
              )}
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
                <input 
                  type="text" 
                  value={singlePhone}
                  onChange={e => setSinglePhone(e.target.value)}
                  placeholder="+919876543210"
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Message</label>
                <textarea 
                  value={singleMessage}
                  onChange={e => setSingleMessage(e.target.value)}
                  placeholder="Type your message here..."
                  rows={4}
                  className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none resize-none"
                  required
                />
              </div>
              
              <button 
                type="submit" 
                disabled={isSendingSingle || !singlePhone || !singleMessage}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSendingSingle ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                {isSendingSingle ? 'Sending...' : 'Send Message'}
              </button>
            </form>
          </div>
        </div>

        {/* Bulk Upload Form */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-100 bg-gray-50 px-6 py-4">
            <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-gray-500" /> Bulk Send via Excel
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

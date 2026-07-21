import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/axios';
import { TestTube, Plus, Trash2, Loader2, Upload, MessageSquare, ChevronDown, ChevronUp } from 'lucide-react';

export default function LabTestsPage() {
  const { hospitalId } = useParams();
  const [tests, setTests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Form & Edit State
  const [editingTest, setEditingTest] = useState<any>(null);
  const [name, setName] = useState('');
  const [category, setCategory] = useState('');
  const [price, setPrice] = useState('');
  const [prerequisites, setPrerequisites] = useState('');
  const [expandedRowId, setExpandedRowId] = useState<number | null>(null);
  const [tempNote, setTempNote] = useState('');

  const fetchTests = async () => {
    try {
      const res = await api.get(`/lab-tests/hospital/${hospitalId}`);
      setTests(res.data);
    } catch (err) {
      console.error("Failed to fetch lab tests", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTests(); }, [hospitalId]);

  const handleEditClick = (test: any) => {
    setEditingTest(test);
    setName(test.name);
    setCategory(test.category || '');
    setPrice(test.price || '');
    setPrerequisites(test.prerequisites || '');
  };

  const cancelEdit = () => {
    setEditingTest(null);
    setName('');
    setCategory('');
    setPrice('');
    setPrerequisites('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingTest) {
        await api.patch(`/lab-tests/${editingTest.id}`, {
          name,
          category,
          price: parseFloat(price) || 0,
          prerequisites
        });
      } else {
        await api.post('/lab-tests/', {
          hospital_id: Number(hospitalId),
          name,
          category,
          price: parseFloat(price) || 0,
          prerequisites
        });
      }
      cancelEdit();
      fetchTests();
    } catch (err) {
      alert(editingTest ? "Failed to update test" : "Failed to add test");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Remove this lab test?")) return;
    try {
      await api.delete(`/lab-tests/${id}`);
      fetchTests();
    } catch (err) {
      alert("Failed to delete");
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      setLoading(true);
      await api.post(`/lab-tests/hospital/${hospitalId}/bulk-upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      alert("Lab tests imported successfully!");
      fetchTests();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Import failed. Ensure it's a valid CSV.");
    } finally {
      setLoading(false);
      event.target.value = ''; 
    }
  };

  const handleToggleOutsourced = async (test: any) => {
    const isOutsourcedNow = !test.is_outsourced;
    const payload: any = { is_outsourced: isOutsourcedNow };
    
    // Clear note if turned off
    if (!isOutsourcedNow && test.outsourced_note) {
      payload.outsourced_note = null;
    }
    
    try {
      await api.patch(`/lab-tests/${test.id}`, payload);
      // Update local state without full reload
      setTests(tests.map(t => t.id === test.id ? { ...t, ...payload } : t));
    } catch (err) {
      alert("Failed to update status");
    }
  };

  const handleSaveNote = async (testId: number) => {
    try {
      // Use null instead of empty string if clearing it out
      const noteToSave = tempNote.trim() || null;
      await api.patch(`/lab-tests/${testId}`, { outsourced_note: noteToSave });
      setTests(tests.map(t => t.id === testId ? { ...t, outsourced_note: noteToSave } : t));
      setExpandedRowId(null);
    } catch (err) {
      alert("Failed to save note");
    }
  };

  const handleExpand = (test: any) => {
    if (expandedRowId === test.id) {
      setExpandedRowId(null);
    } else {
      setExpandedRowId(test.id);
      setTempNote(test.outsourced_note || '');
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">

      <div className="flex justify-between items-center border-b pb-4">
        <div className="flex items-center gap-3">
          <TestTube className="w-6 h-6 text-purple-600" />
          <h2 className="text-2xl font-bold text-gray-900">Lab & Diagnostics</h2>
        </div>

        <div className="relative">
          <input type="file" id="lab-upload" className="hidden" onChange={handleFileUpload} accept=".csv" disabled={loading} />
          <label htmlFor="lab-upload" className={`flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 cursor-pointer font-medium text-sm transition-colors ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            Import CSV
          </label>
        </div>
      </div>

      {/* Add / Edit Test Form */}
      <form onSubmit={handleSubmit} className={`p-6 rounded-xl shadow-sm border grid grid-cols-1 md:grid-cols-4 gap-4 items-end transition-colors ${editingTest ? 'bg-purple-50 border-purple-200' : 'bg-white border-gray-200'}`}>
        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-gray-700 mb-1">Test Name *</label>
          <input required type="text" value={name} onChange={e => setName(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm bg-white" placeholder="e.g. Complete Blood Count (CBC)" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Category</label>
          <input type="text" value={category} onChange={e => setCategory(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm bg-white" placeholder="e.g. Blood Test" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Price (₹)</label>
          <input type="number" step="0.01" value={price} onChange={e => setPrice(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm bg-white" placeholder="0.00" />
        </div>
        <div className="md:col-span-3">
          <label className="block text-xs font-medium text-gray-700 mb-1">Preparation / Prerequisites (AI will read this to patients)</label>
          <input type="text" value={prerequisites} onChange={e => setPrerequisites(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm bg-white" placeholder="e.g. Fasting required for 8-10 hours. Water is allowed." />
        </div>
        <div className="flex gap-2">
          <button type="submit" className="flex-1 flex items-center justify-center gap-2 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 text-sm font-medium">
            {editingTest ? "Update" : <><Plus className="w-4 h-4" /> Add Test</>}
          </button>
          {editingTest && (
            <button type="button" onClick={cancelEdit} className="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300 text-sm font-medium">
              Cancel
            </button>
          )}
        </div>
      </form>

      {/* Tests Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-12 flex justify-center text-purple-600"><Loader2 className="w-6 h-6 animate-spin" /></div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 border-b text-gray-500 uppercase text-xs">
              <tr>
                <th className="p-4">Test Name</th>
                <th className="p-4">Category</th>
                <th className="p-4">Price</th>
                <th className="p-4">Prerequisites</th>
                <th className="p-4">Outsourced</th>
                <th className="p-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {tests.map(test => (
                <React.Fragment key={test.id}>
                  <tr className={`hover:bg-gray-50 ${expandedRowId === test.id ? 'bg-gray-50' : ''}`}>
                    <td className="p-4 font-medium">{test.name}</td>
                    <td className="p-4 text-gray-500">{test.category || '-'}</td>
                    <td className="p-4">₹{test.price}</td>
                    <td className="p-4 text-gray-600 text-xs">{test.prerequisites || 'None'}</td>
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input 
                            type="checkbox" 
                            className="sr-only peer" 
                            checked={!!test.is_outsourced} 
                            onChange={() => handleToggleOutsourced(test)} 
                          />
                          <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600"></div>
                        </label>
                        {!!test.outsourced_note && (
                          <MessageSquare className="w-4 h-4 text-purple-600" title="Has Note" />
                        )}
                      </div>
                    </td>
                    <td className="p-4 flex items-center gap-3">
                      <button onClick={() => handleEditClick(test)} className="text-purple-600 hover:text-purple-800 text-sm font-medium">Edit</button>
                      <button onClick={() => handleDelete(test.id)} className="text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
                      <button 
                        onClick={() => handleExpand(test)} 
                        className="text-gray-400 hover:text-gray-600 ml-2"
                        title="Add/Edit Outsourced Note"
                      >
                        {expandedRowId === test.id ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                      </button>
                    </td>
                  </tr>
                  {expandedRowId === test.id && (
                    <tr className="bg-gray-50 border-b border-gray-100">
                      <td colSpan={6} className="p-4 pl-8 pb-6">
                        <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm w-full max-w-2xl">
                          <label className="block text-xs font-semibold text-gray-700 mb-2">Outsourced Note (Optional)</label>
                          <textarea
                            value={tempNote}
                            onChange={(e) => setTempNote(e.target.value)}
                            placeholder="e.g. This test is processed by an external lab..."
                            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white min-h-[80px] focus:ring-1 focus:ring-purple-500 focus:border-purple-500"
                          />
                          <div className="flex gap-2 mt-3 justify-end">
                            <button onClick={() => setExpandedRowId(null)} className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded-md transition-colors">Cancel</button>
                            <button onClick={() => handleSaveNote(test.id)} className="px-3 py-1.5 text-xs font-medium bg-purple-600 text-white hover:bg-purple-700 rounded-md transition-colors">Save Note</button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
              {tests.length === 0 && (
                <tr><td colSpan={6} className="p-8 text-center text-gray-400">No lab tests added yet.</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
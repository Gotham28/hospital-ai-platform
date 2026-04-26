import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/axios';
import { TestTube, Plus, Trash2, Loader2, Upload } from 'lucide-react';

export default function LabTestsPage() {
  const { hospitalId } = useParams();
  const [tests, setTests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Form State
  const [name, setName] = useState('');
  const [category, setCategory] = useState('');
  const [price, setPrice] = useState('');
  const [prerequisites, setPrerequisites] = useState('');

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

  const handleAddTest = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/lab-tests/', {
        hospital_id: Number(hospitalId),
        name,
        category,
        price: parseFloat(price) || 0,
        prerequisites
      });
      setName(''); setCategory(''); setPrice(''); setPrerequisites('');
      fetchTests();
    } catch (err) {
      alert("Failed to add test");
    }
  };

  const handleDelete = async (id: int) => {
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

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center gap-3 border-b pb-4">
        <TestTube className="w-6 h-6 text-purple-600" />
        <h2 className="text-2xl font-bold text-gray-900">Lab & Diagnostics</h2>
      </div>
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

      {/* Add New Test Form */}
      <form onSubmit={handleAddTest} className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-gray-700 mb-1">Test Name *</label>
          <input required type="text" value={name} onChange={e => setName(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="e.g. Complete Blood Count (CBC)" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Category</label>
          <input type="text" value={category} onChange={e => setCategory(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="e.g. Blood Test" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Price ($)</label>
          <input type="number" step="0.01" value={price} onChange={e => setPrice(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="0.00" />
        </div>
        <div className="md:col-span-3">
          <label className="block text-xs font-medium text-gray-700 mb-1">Preparation / Prerequisites (AI will read this to patients)</label>
          <input type="text" value={prerequisites} onChange={e => setPrerequisites(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="e.g. Fasting required for 8-10 hours. Water is allowed." />
        </div>
        <div>
          <button type="submit" className="w-full flex items-center justify-center gap-2 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 text-sm font-medium">
            <Plus className="w-4 h-4" /> Add Test
          </button>
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
                <th className="p-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {tests.map(test => (
                <tr key={test.id} className="hover:bg-gray-50">
                  <td className="p-4 font-medium">{test.name}</td>
                  <td className="p-4 text-gray-500">{test.category || '-'}</td>
                  <td className="p-4">${test.price}</td>
                  <td className="p-4 text-gray-600 text-xs">{test.prerequisites || 'None'}</td>
                  <td className="p-4">
                    <button onClick={() => handleDelete(test.id)} className="text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
                  </td>
                </tr>
              ))}
              {tests.length === 0 && (
                <tr><td colSpan={5} className="p-8 text-center text-gray-400">No lab tests added yet.</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
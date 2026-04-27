import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/axios';
import { Pill, Plus, Trash2, Loader2, Upload } from 'lucide-react';

export default function PharmacyPage() {
  const { hospitalId } = useParams();
  const [medicines, setMedicines] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Form & Edit State
  const [editingMed, setEditingMed] = useState<any>(null);
  const [name, setName] = useState('');
  const [brand, setBrand] = useState('');
  const [price, setPrice] = useState('');
  const [rxRequired, setRxRequired] = useState(false);

  const fetchMedicines = async () => {
    try {
      const res = await api.get(`/medicines/hospital/${hospitalId}`);
      setMedicines(res.data);
    } catch (err) {
      console.error("Failed to fetch medicines", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchMedicines(); }, [hospitalId]);

  const handleEditClick = (med: any) => {
    setEditingMed(med);
    setName(med.name);
    setBrand(med.brand_name || '');
    setPrice(med.price || '');
    setRxRequired(med.requires_prescription);
  };

  const cancelEdit = () => {
    setEditingMed(null);
    setName('');
    setBrand('');
    setPrice('');
    setRxRequired(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingMed) {
        await api.patch(`/medicines/${editingMed.id}`, {
          name,
          brand_name: brand,
          price: parseFloat(price) || 0,
          requires_prescription: rxRequired
        });
      } else {
        await api.post('/medicines/', {
          hospital_id: Number(hospitalId),
          name,
          brand_name: brand,
          price: parseFloat(price) || 0,
          requires_prescription: rxRequired
        });
      }
      cancelEdit();
      fetchMedicines();
    } catch (err) {
      alert(editingMed ? "Failed to update medicine" : "Failed to add medicine");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Remove this medicine?")) return;
    try {
      await api.delete(`/medicines/${id}`);
      fetchMedicines();
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
      await api.post(`/medicines/hospital/${hospitalId}/bulk-upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      alert("Pharmacy inventory imported successfully!");
      fetchMedicines();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Import failed. Ensure it's a valid CSV.");
    } finally {
      setLoading(false);
      event.target.value = ''; // Reset input
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">

      <div className="flex justify-between items-center border-b pb-4">
        <div className="flex items-center gap-3">
          <Pill className="w-6 h-6 text-blue-600" />
          <h2 className="text-2xl font-bold text-gray-900">Pharmacy Inventory</h2>
        </div>
        
        <div className="relative">
          <input type="file" id="pharmacy-upload" className="hidden" onChange={handleFileUpload} accept=".csv" disabled={loading} />
          <label htmlFor="pharmacy-upload" className={`flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 cursor-pointer font-medium text-sm transition-colors ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            Import CSV
          </label>
        </div>
      </div>

      {/* Add / Edit Medicine Form */}
      <form onSubmit={handleSubmit} className={`p-6 rounded-xl shadow-sm border grid grid-cols-1 md:grid-cols-5 gap-4 items-end transition-colors ${editingMed ? 'bg-blue-50 border-blue-200' : 'bg-white border-gray-200'}`}>
        <div className="md:col-span-2">
          <label className="block text-xs font-medium text-gray-700 mb-1">Generic Name *</label>
          <input required type="text" value={name} onChange={e => setName(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm bg-white" placeholder="e.g. Paracetamol" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Brand Name</label>
          <input type="text" value={brand} onChange={e => setBrand(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm bg-white" placeholder="e.g. Tylenol" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Price (₹)</label>
          <input type="number" step="0.01" value={price} onChange={e => setPrice(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm bg-white" placeholder="0.00" />
        </div>
        <div className="flex flex-col gap-2">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={rxRequired} onChange={e => setRxRequired(e.target.checked)} />
            Requires Rx
          </label>
          <div className="flex gap-2">
            <button type="submit" className="flex-1 flex items-center justify-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm font-medium">
              {editingMed ? "Update" : <><Plus className="w-4 h-4" /> Add</>}
            </button>
            {editingMed && (
              <button type="button" onClick={cancelEdit} className="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300 text-sm font-medium">
                Cancel
              </button>
            )}
          </div>
        </div>
      </form>

      {/* Inventory Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-12 flex justify-center text-blue-600"><Loader2 className="w-6 h-6 animate-spin" /></div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 border-b text-gray-500 uppercase text-xs">
              <tr>
                <th className="p-4">Name</th>
                <th className="p-4">Brand</th>
                <th className="p-4">Price</th>
                <th className="p-4">Prescription</th>
                <th className="p-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {medicines.map(med => (
                <tr key={med.id} className="hover:bg-gray-50">
                  <td className="p-4 font-medium">{med.name}</td>
                  <td className="p-4 text-gray-500">{med.brand_name || '-'}</td>
                  <td className="p-4">₹{med.price}</td>
                  <td className="p-4">{med.requires_prescription ? <span className="text-red-600 font-medium text-xs bg-red-50 px-2 py-1 rounded">Yes</span> : <span className="text-green-600 font-medium text-xs bg-green-50 px-2 py-1 rounded">No</span>}</td>
                  <td className="p-4 flex items-center gap-3">
                    <button onClick={() => handleEditClick(med)} className="text-blue-600 hover:text-blue-800 text-sm font-medium">Edit</button>
                    <button onClick={() => handleDelete(med.id)} className="text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
                  </td>
                </tr>
              ))}
              {medicines.length === 0 && (
                <tr><td colSpan={5} className="p-8 text-center text-gray-400">No medicines added yet.</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
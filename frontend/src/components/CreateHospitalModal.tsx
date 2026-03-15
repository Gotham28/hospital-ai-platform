import { useState } from 'react';
import api from '../api/axios'; // Use your centralized API config
import { X } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void; 
}

export default function CreateHospitalModal({ isOpen, onClose, onSuccess }: Props) {
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    address: '',
    is_active: true,
    // Ensure these match your new Backend Schema (HospitalCreate)
    system_prompt: 'You are Arogya, a helpful assistant for this hospital.',
    google_sheet_id: ''
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Logic: This will now use https://hospital-ai-platform.onrender.com/api/v1/hospitals/
      await api.post('/hospitals/', formData);
      
      onSuccess(); // Refresh the list
      onClose();   // Close the modal
      
      // Reset form
      setFormData({ 
        name: '', 
        slug: '', 
        address: '', 
        is_active: true,
        system_prompt: 'You are Arogya, a helpful assistant for this hospital.',
        google_sheet_id: ''
      });
    } catch (err: any) {
      console.error("Submission Error:", err.response?.data);
      // If the backend returns a specific error (like 'Slug already exists'), show it
      const errorMessage = err.response?.data?.detail;
      setError(Array.isArray(errorMessage) ? 'Validation Error' : (errorMessage || 'Failed to create hospital'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
          <h3 className="font-semibold text-gray-800">Add New Hospital</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 text-red-600 text-sm rounded-md">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Hospital Name</label>
            <input
              required
              type="text"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={formData.name}
              onChange={e => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g. Arogya Specialty"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Slug (Unique ID)</label>
            <input
              required
              type="text"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={formData.slug}
              onChange={e => setFormData({ ...formData, slug: e.target.value.toLowerCase().replace(/\s+/g, '-') })}
              placeholder="e.g. arogya-specialty"
            />
            <p className="text-xs text-gray-400 mt-1">Must be unique. No spaces.</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
            <textarea
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={formData.address}
              onChange={e => setFormData({ ...formData, address: e.target.value })}
              rows={2}
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-md"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50"
            >
              {loading ? 'Connecting to Cloud...' : 'Create Hospital'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
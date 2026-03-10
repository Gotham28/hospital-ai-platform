import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/axios';
import { Search, Loader2, Upload, Users } from 'lucide-react';

const DoctorsPage = () => {
  const { hospitalId } = useParams();
  const [doctors, setDoctors] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDoctors = async () => {
    try {
      const res = await api.get(`/hospitals/${hospitalId}/doctors`);
      setDoctors(res.data);
    } catch (err) {
      console.error("Failed to fetch doctors", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDoctors();
  }, [hospitalId]);

  // Automatic Bulk Upload Handler
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      setLoading(true);
      // This hits the backend endpoint that generates IDs automatically
      await api.post(`/hospitals/${hospitalId}/doctors/bulk-upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      alert("Doctors imported successfully! IDs have been assigned automatically.");
      fetchDoctors(); // Refresh the list to show new IDs
    } catch (err) {
      alert("Import failed. Ensure the file format is correct.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Doctor Directory</h2>
          <p className="text-gray-500 text-sm">Upload your staff list; IDs are assigned automatically for AI syncing.</p>
        </div>
        
        {/* Bulk Upload Button (Replaces manual inputs) */}
        <div className="relative">
          <input 
            type="file" 
            id="bulk-upload" 
            className="hidden" 
            onChange={handleFileUpload} 
            accept=".csv,.txt"
            disabled={loading}
          />
          <label 
            htmlFor="bulk-upload" 
            className={`flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors cursor-pointer font-medium shadow-sm ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            Upload Staff Document
          </label>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-100 bg-gray-50 flex items-center gap-3">
          <Search className="w-5 h-5 text-gray-400" />
          <input 
            type="text" 
            placeholder="Search doctors or specialties..." 
            className="bg-transparent border-none focus:ring-0 text-sm w-full"
          />
        </div>

        {loading ? (
          <div className="p-20 flex flex-col items-center justify-center text-gray-400">
            <Loader2 className="animate-spin mb-2" />
            <p>Syncing directory...</p>
          </div>
        ) : doctors.length === 0 ? (
          <div className="p-20 text-center">
            <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-4">
              <Users className="w-8 h-8 text-blue-200" />
            </div>
            <h3 className="text-lg font-medium text-gray-900">No doctors found</h3>
            <p className="text-gray-500 max-w-xs mx-auto mt-1">
              Upload your hospital staff list to begin. IDs will be generated for your Google Sheet.
            </p>
          </div>
        ) : (
          <table className="w-full text-left">
            <thead className="bg-gray-50 text-xs uppercase text-gray-500 font-semibold border-b">
              <tr>
                <th className="p-4">Auto-Generated ID</th>
                <th className="p-4">Name</th>
                <th className="p-4">Department</th>
                <th className="p-4">Connection Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {doctors.map((doc: any) => (
                <tr key={doc.id} className="hover:bg-gray-50 transition-colors">
                  <td className="p-4 font-mono text-sm text-blue-600 font-bold">{doc.doctor_id}</td>
                  <td className="p-4 text-sm font-medium text-gray-900">{doc.name}</td>
                  <td className="p-4 text-sm text-gray-500">{doc.department || 'General'}</td>
                  <td className="p-4">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      Active & Ready
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default DoctorsPage;
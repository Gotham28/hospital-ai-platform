import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/axios';
import { UserPlus, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function SettingsPage() {
  const { hospitalId } = useParams();
  const { role } = useAuth();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleCreateStaff = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      await api.post(`/hospitals/${hospitalId}/staff`, {
        full_name: fullName,
        email,
        password,
      });
      setSuccess(`Staff account for ${fullName} created successfully!`);
      setFullName('');
      setEmail('');
      setPassword('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create staff account.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Hospital Settings</h2>
        <p className="text-sm text-gray-500 mt-1">Manage configuration and staff access for this hospital.</p>
      </div>

      {role === 'superadmin' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <UserPlus className="w-5 h-5 text-blue-600" /> Add Staff Member
            </h3>
            <p className="text-sm text-gray-500 mt-1">
              Create credentials for receptionists or admins to manage appointments.
            </p>
          </div>

          <form onSubmit={handleCreateStaff} className="p-6 space-y-4">
            {error && (
              <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm flex items-center gap-2 border border-red-100">
                <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
              </div>
            )}
            {success && (
              <div className="p-3 bg-emerald-50 text-emerald-700 rounded-lg text-sm flex items-center gap-2 border border-emerald-100">
                <CheckCircle2 className="w-4 h-4 flex-shrink-0" /> {success}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                <input
                  type="text" required value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  placeholder="e.g. Front Desk"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                <input
                  type="email" required value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  placeholder="staff@hospital.com"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Temporary Password</label>
              <input
                type="password" required minLength={6} value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="Minimum 6 characters"
              />
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={loading || !fullName || !email || !password}
                className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
                Create Account
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
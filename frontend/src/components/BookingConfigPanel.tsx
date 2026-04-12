import React, { useState, useEffect } from 'react';
import api from '../api/axios';
import { Save, Info } from 'lucide-react';

interface BookingConfig {
  bookable_departments: string[];
  min_advance_hours: number;
  max_per_doctor_per_day: number;
  notification_email: string;
  reminder_hours_before: number;
}

export default function BookingConfigPanel({ hospitalId, allDepartments }: {
  hospitalId: number;
  allDepartments: string[];   // pass in from parent (fetched from /hospitals/{id}/doctors)
}) {
  const [config, setConfig] = useState<BookingConfig>({
    bookable_departments: [],
    min_advance_hours: 2,
    max_per_doctor_per_day: 20,
    notification_email: '',
    reminder_hours_before: 24,
  });
  const [loading, setLoading]   = useState(false);
  const [saving, setSaving]     = useState(false);
  const [saved, setSaved]       = useState(false);

  useEffect(() => {
    setLoading(true);
    api.get(`/appointments/config/${hospitalId}`)
      .then(res => setConfig(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [hospitalId]);

  const toggleDept = (dept: string) => {
    setConfig(c => ({
      ...c,
      bookable_departments: c.bookable_departments.includes(dept)
        ? c.bookable_departments.filter(d => d !== dept)
        : [...c.bookable_departments, dept],
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.patch(`/appointments/config/${hospitalId}`, config);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      console.error('Save failed', e);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-gray-400 text-sm py-4">Loading booking config…</div>;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h3 className="text-lg font-bold text-gray-900">Booking Configuration</h3>
        <p className="text-sm text-gray-500 mt-1">
          Control how Arogya handles appointment booking for this hospital.
        </p>
      </div>

      {/* Notification email */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Staff Notification Email
        </label>
        <input type="email" value={config.notification_email}
          onChange={e => setConfig(c => ({ ...c, notification_email: e.target.value }))}
          placeholder="reception@hospital.com"
          className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        <p className="text-xs text-gray-400 mt-1">
          New appointment requests and approvals will be emailed here.
        </p>
      </div>

      {/* Bookable departments */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Bookable Departments
        </label>
        <div className="flex items-start gap-2 mb-3 p-3 bg-blue-50 rounded-lg">
          <Info className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
          <p className="text-xs text-blue-700">
            Leave all unchecked to allow booking for all departments.
            Check specific ones to restrict booking to only those.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {allDepartments.length === 0 && (
            <p className="text-sm text-gray-400">No departments found. Add doctors first.</p>
          )}
          {allDepartments.map(dept => (
            <button key={dept} onClick={() => toggleDept(dept)}
              className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                config.bookable_departments.includes(dept)
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'
              }`}>
              {dept}
            </button>
          ))}
        </div>
      </div>

      {/* Min advance hours */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Minimum Advance Notice (hours)
        </label>
        <input type="number" min={0} max={72} value={config.min_advance_hours}
          onChange={e => setConfig(c => ({ ...c, min_advance_hours: parseInt(e.target.value) || 0 }))}
          className="w-32 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        <p className="text-xs text-gray-400 mt-1">
          Patients cannot book within this many hours of their preferred date.
        </p>
      </div>

      {/* Max per doctor per day */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Max Appointments per Doctor per Day
        </label>
        <input type="number" min={1} max={100} value={config.max_per_doctor_per_day}
          onChange={e => setConfig(c => ({ ...c, max_per_doctor_per_day: parseInt(e.target.value) || 1 }))}
          className="w-32 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>

      {/* Save */}
      <button onClick={handleSave} disabled={saving}
        className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40 text-sm font-medium">
        <Save className="w-4 h-4" />
        {saving ? 'Saving…' : saved ? '✓ Saved!' : 'Save Configuration'}
      </button>
    </div>
  );
}
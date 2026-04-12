import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/axios';
import { CheckCircle, XCircle, Clock, Phone, User, Calendar, Stethoscope, RefreshCw } from 'lucide-react';

interface Appointment {
  id: number;
  reference_number: string;
  patient_name: string;
  patient_age: string;
  patient_phone: string;
  doctor_name: string;
  doctor_department: string;
  preferred_date: string;
  time_of_day: string;
  status: 'pending' | 'approved' | 'rejected';
  confirmed_time: string | null;
  rejection_reason: string | null;
  created_at: string;
}

const REJECTION_REASONS = [
  'Doctor on leave',
  'No slots available on this date',
  'Please call reception to book',
  'Outside working hours',
  'Department not available',
];

const STATUS_STYLES = {
  pending:  'bg-amber-100 text-amber-700 border-amber-200',
  approved: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  rejected: 'bg-red-100 text-red-700 border-red-200',
};

const TIME_LABELS: Record<string, string> = {
  morning:   '🌅 Morning',
  afternoon: '☀️ Afternoon',
  evening:   '🌇 Evening',
};

export default function AppointmentsTab() {
  const { hospitalId } = useParams<{ hospitalId: string }>();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved' | 'rejected'>('pending');
  const [loading, setLoading] = useState(false);
  const [approveModal, setApproveModal] = useState<Appointment | null>(null);
  const [rejectModal, setRejectModal]   = useState<Appointment | null>(null);
  const [confirmedTime, setConfirmedTime]   = useState('');
  const [rejectionReason, setRejectionReason] = useState(REJECTION_REASONS[0]);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchAppointments = useCallback(async () => {
    if (!hospitalId) return;
    setLoading(true);
    try {
      const params = filter !== 'all' ? `?status=${filter}` : '';
      const res = await api.get(`/appointments/hospital/${hospitalId}${params}`);
      setAppointments(res.data);
    } catch (e) {
      console.error('Failed to fetch appointments', e);
    } finally {
      setLoading(false);
    }
  }, [hospitalId, filter]);

  useEffect(() => {
    fetchAppointments();
    // Poll every 30 seconds for new requests
    const interval = setInterval(fetchAppointments, 30_000);
    return () => clearInterval(interval);
  }, [fetchAppointments]);

  const handleApprove = async () => {
    if (!approveModal || !confirmedTime.trim()) return;
    setActionLoading(true);
    try {
      await api.patch(`/appointments/${approveModal.id}/approve`, { confirmed_time: confirmedTime });
      setApproveModal(null);
      setConfirmedTime('');
      fetchAppointments();
    } catch (e) {
      console.error('Approve failed', e);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!rejectModal) return;
    setActionLoading(true);
    try {
      await api.patch(`/appointments/${rejectModal.id}/reject`, { reason: rejectionReason });
      setRejectModal(null);
      fetchAppointments();
    } catch (e) {
      console.error('Reject failed', e);
    } finally {
      setActionLoading(false);
    }
  };

  const pendingCount = appointments.filter(a => a.status === 'pending').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Appointments</h2>
          {pendingCount > 0 && (
            <p className="text-sm text-amber-600 font-medium mt-1">
              ⚠️ {pendingCount} pending request{pendingCount > 1 ? 's' : ''} need attention
            </p>
          )}
        </div>
        <button onClick={fetchAppointments}
          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 border-b">
        {(['pending', 'approved', 'rejected', 'all'] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-4 py-2 text-sm font-medium capitalize border-b-2 transition-colors ${
              filter === f ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}>
            {f}
          </button>
        ))}
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading…</div>
      ) : appointments.length === 0 ? (
        <div className="text-center py-12 text-gray-400">No {filter} appointments.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs uppercase text-gray-500 font-semibold border-b">
              <tr>
                <th className="p-4 text-left">Reference</th>
                <th className="p-4 text-left">Patient</th>
                <th className="p-4 text-left">Doctor</th>
                <th className="p-4 text-left">Date & Time</th>
                <th className="p-4 text-left">Status</th>
                <th className="p-4 text-left">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {appointments.map(appt => (
                <tr key={appt.id} className="hover:bg-gray-50">
                  <td className="p-4 font-mono text-xs text-blue-600">{appt.reference_number}</td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <User className="w-4 h-4 text-gray-400" />
                      <div>
                        <p className="font-medium text-gray-900">{appt.patient_name}</p>
                        <p className="text-xs text-gray-500">Age: {appt.patient_age}</p>
                        <p className="text-xs text-gray-500 flex items-center gap-1">
                          <Phone className="w-3 h-3" />{appt.patient_phone}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <Stethoscope className="w-4 h-4 text-gray-400" />
                      <div>
                        <p className="font-medium text-gray-900">{appt.doctor_name}</p>
                        <p className="text-xs text-gray-500">{appt.doctor_department}</p>
                      </div>
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-gray-400" />
                      <div>
                        <p className="font-medium">{appt.preferred_date}</p>
                        <p className="text-xs text-gray-500">{TIME_LABELS[appt.time_of_day] || appt.time_of_day}</p>
                        {appt.confirmed_time && (
                          <p className="text-xs text-emerald-600 font-medium">✓ {appt.confirmed_time}</p>
                        )}
                        {appt.rejection_reason && (
                          <p className="text-xs text-red-500">{appt.rejection_reason}</p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="p-4">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium border capitalize ${STATUS_STYLES[appt.status]}`}>
                      {appt.status === 'pending'  && <Clock className="w-3 h-3" />}
                      {appt.status === 'approved' && <CheckCircle className="w-3 h-3" />}
                      {appt.status === 'rejected' && <XCircle className="w-3 h-3" />}
                      {appt.status}
                    </span>
                  </td>
                  <td className="p-4">
                    {appt.status === 'pending' && (
                      <div className="flex gap-2">
                        <button onClick={() => { setApproveModal(appt); setConfirmedTime(''); }}
                          className="px-3 py-1 text-xs bg-emerald-600 text-white rounded-md hover:bg-emerald-700">
                          Approve
                        </button>
                        <button onClick={() => { setRejectModal(appt); setRejectionReason(REJECTION_REASONS[0]); }}
                          className="px-3 py-1 text-xs border border-red-300 text-red-600 rounded-md hover:bg-red-50">
                          Reject
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Approve Modal */}
      {approveModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h3 className="text-lg font-bold text-gray-900">Approve Appointment</h3>
            <p className="text-sm text-gray-600">
              Approving <strong>{approveModal.reference_number}</strong> for <strong>{approveModal.patient_name}</strong> with <strong>{approveModal.doctor_name}</strong> on <strong>{approveModal.preferred_date}</strong>.
            </p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirmed Time</label>
              <input type="text" value={confirmedTime} onChange={e => setConfirmedTime(e.target.value)}
                placeholder="e.g. 10:30 AM"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500" />
              <p className="text-xs text-gray-400 mt-1">Staff will be reminded to call the patient at {approveModal.patient_phone}</p>
            </div>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setApproveModal(null)}
                className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">Cancel</button>
              <button onClick={handleApprove} disabled={!confirmedTime.trim() || actionLoading}
                className="px-4 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-40">
                {actionLoading ? 'Saving…' : 'Confirm Approval'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {rejectModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h3 className="text-lg font-bold text-gray-900">Reject Appointment</h3>
            <p className="text-sm text-gray-600">
              Rejecting <strong>{rejectModal.reference_number}</strong> for <strong>{rejectModal.patient_name}</strong>.
            </p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Reason</label>
              <select value={rejectionReason} onChange={e => setRejectionReason(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400">
                {REJECTION_REASONS.map(r => <option key={r}>{r}</option>)}
              </select>
            </div>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setRejectModal(null)}
                className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">Cancel</button>
              <button onClick={handleReject} disabled={actionLoading}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-40">
                {actionLoading ? 'Saving…' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
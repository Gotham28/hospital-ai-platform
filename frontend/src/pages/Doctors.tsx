import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import api from '../api/axios';
import { Search, Loader2, Upload, Users, CalendarDays, Clock, Trash2, Plus, X } from 'lucide-react';

const DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

export default function DoctorsPage() {
  const { hospitalId } = useParams();
  const [doctors, setDoctors] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Main Form & Edit State
  const [editingDoc, setEditingDoc] = useState<any>(null);
  const [docName, setDocName] = useState('');
  const [docDept, setDocDept] = useState('');
  const [docSchedule, setDocSchedule] = useState('');

  // Modal State
  const [manageDoc, setManageDoc] = useState<any>(null);
  const [schedules, setSchedules] = useState<any[]>([]);
  const [leaves, setLeaves] = useState<any[]>([]);
  
  // Modal Form State
  const [schedDay, setSchedDay] = useState('0');
  const [schedStart, setSchedStart] = useState('09:00');
  const [schedEnd, setSchedEnd] = useState('17:00');
  const [leaveDate, setLeaveDate] = useState('');
  const [leaveReason, setLeaveReason] = useState('');

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

  useEffect(() => { fetchDoctors(); }, [hospitalId]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      setLoading(true);
      await api.post(`/hospitals/${hospitalId}/doctors/bulk-upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      alert("Staff imported and AI-mapped successfully!");
      fetchDoctors();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Import failed. Ensure it's a valid CSV.");
    } finally {
      setLoading(false);
      event.target.value = '';
    }
  };

  // --- Doctor Core Management (Add, Edit, Delete) ---

  const handleEditClick = (doc: any) => {
    setEditingDoc(doc);
    setDocName(doc.name);
    setDocDept(doc.department || '');
    setDocSchedule(doc.base_schedule || '');
  };

  const cancelDocEdit = () => {
    setEditingDoc(null);
    setDocName('');
    setDocDept('');
    setDocSchedule('');
  };

  const handleDocSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingDoc) {
        await api.patch(`/hospitals/${hospitalId}/doctors/${editingDoc.id}`, {
          name: docName,
          department: docDept,
          base_schedule: docSchedule
        });
      } else {
        // Automatically generate a doctor_id for manual creations
        await api.post(`/hospitals/${hospitalId}/doctors`, {
          name: docName,
          department: docDept,
          base_schedule: docSchedule,
          doctor_id: `H${hospitalId}-D-${Math.floor(Math.random() * 10000)}`
        });
      }
      cancelDocEdit();
      fetchDoctors();
    } catch (err) {
      alert(editingDoc ? "Failed to update doctor" : "Failed to add doctor");
    }
  };

  const deleteDoctor = async (id: number) => {
    if (!confirm("Remove this doctor and all their schedules?")) return;
    try {
      await api.delete(`/hospitals/${hospitalId}/doctors/${id}`);
      fetchDoctors();
    } catch (err) {
      alert("Failed to delete doctor");
    }
  };

  // --- Detailed Availability Management ---

  const openManageModal = async (doc: any) => {
    setManageDoc(doc);
    fetchAvailability(doc.id);
  };

  const fetchAvailability = async (doctorId: number) => {
    try {
      const [schedRes, leaveRes] = await Promise.all([
        api.get(`/availability/schedules/doctor/${doctorId}`),
        api.get(`/availability/leaves/doctor/${doctorId}`)
      ]);
      setSchedules(schedRes.data);
      setLeaves(leaveRes.data);
    } catch (err) {
      console.error("Failed to load availability", err);
    }
  };

  const handleAddSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/availability/schedules/', {
        doctor_id: manageDoc.id,
        day_of_week: parseInt(schedDay),
        start_time: schedStart,
        end_time: schedEnd
      });
      fetchAvailability(manageDoc.id);
    } catch (err) { alert("Failed to add schedule"); }
  };

  const handleAddLeave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/availability/leaves/', {
        doctor_id: manageDoc.id,
        date: leaveDate,
        reason: leaveReason
      });
      setLeaveDate(''); setLeaveReason('');
      fetchAvailability(manageDoc.id);
    } catch (err) { alert("Failed to add leave"); }
  };

  const deleteSchedule = async (id: number) => {
    await api.delete(`/availability/schedules/${id}`);
    fetchAvailability(manageDoc.id);
  };

  const deleteLeave = async (id: number) => {
    await api.delete(`/availability/leaves/${id}`);
    fetchAvailability(manageDoc.id);
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Doctor Directory</h2>
          <p className="text-gray-500 text-sm">Manage staff and working hours for AI scheduling.</p>
        </div>
        
        <div className="relative">
          <input type="file" id="bulk-upload" className="hidden" onChange={handleFileUpload} accept=".csv,.txt" disabled={loading} />
          <label htmlFor="bulk-upload" className={`flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 cursor-pointer font-medium shadow-sm transition-colors ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            Upload Staff CSV
          </label>
        </div>
      </div>

      {/* Add / Edit Doctor Form */}
      <form onSubmit={handleDocSubmit} className={`p-6 rounded-xl shadow-sm border grid grid-cols-1 md:grid-cols-4 gap-4 items-end transition-colors ${editingDoc ? 'bg-blue-50 border-blue-200' : 'bg-white border-gray-200'}`}>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Doctor Name *</label>
          <input required type="text" value={docName} onChange={e => setDocName(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm bg-white" placeholder="e.g. John Doe" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Department</label>
          <input type="text" value={docDept} onChange={e => setDocDept(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm bg-white" placeholder="e.g. Cardiology" />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Base Schedule</label>
          <input type="text" value={docSchedule} onChange={e => setDocSchedule(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm bg-white" placeholder="e.g. Mon-Fri 9AM-5PM" />
        </div>
        <div className="flex gap-2">
          <button type="submit" className="flex-1 flex items-center justify-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm font-medium">
            {editingDoc ? "Update" : <><Plus className="w-4 h-4" /> Add Doctor</>}
          </button>
          {editingDoc && (
            <button type="button" onClick={cancelDocEdit} className="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300 text-sm font-medium">
              Cancel
            </button>
          )}
        </div>
      </form>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-100 bg-gray-50 flex items-center gap-3">
          <Search className="w-5 h-5 text-gray-400" />
          <input type="text" placeholder="Search doctors..." className="bg-transparent border-none focus:ring-0 text-sm w-full outline-none" />
        </div>

        {loading ? (
          <div className="p-20 flex justify-center text-blue-600"><Loader2 className="w-8 h-8 animate-spin" /></div>
        ) : doctors.length === 0 ? (
          <div className="p-20 text-center">
            <Users className="w-12 h-12 text-blue-200 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900">No doctors found</h3>
            <p className="text-gray-500 max-w-xs mx-auto mt-1">Upload your hospital staff list to begin.</p>
          </div>
        ) : (
          <table className="w-full text-left">
            <thead className="bg-gray-50 text-xs uppercase text-gray-500 font-semibold border-b">
              <tr>
                <th className="p-4">Name</th>
                <th className="p-4">Department</th>
                <th className="p-4">Base Schedule</th>
                <th className="p-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {doctors.map(doc => (
                <tr key={doc.id} className="hover:bg-gray-50 transition-colors">
                  <td className="p-4 text-sm font-medium text-gray-900">Dr. {doc.name}</td>
                  <td className="p-4 text-sm text-gray-500">{doc.department || 'General'}</td>
                  <td className="p-4 text-sm text-gray-500 truncate max-w-[200px]">{doc.base_schedule || 'Not Specified'}</td>
                  <td className="p-4 flex items-center gap-4">
                    <button onClick={() => openManageModal(doc)} className="text-sm text-emerald-600 font-medium hover:text-emerald-800 flex items-center gap-1">
                      <CalendarDays className="w-4 h-4" /> Manage
                    </button>
                    <button onClick={() => handleEditClick(doc)} className="text-blue-600 hover:text-blue-800 text-sm font-medium">Edit</button>
                    <button onClick={() => deleteDoctor(doc.id)} className="text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* MANAGE SCHEDULE MODAL (Remains unchanged) */}
      {manageDoc && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">
            
            <div className="p-6 border-b flex justify-between items-center bg-gray-50">
              <div>
                <h3 className="text-xl font-bold text-gray-900">Dr. {manageDoc.name}</h3>
                <p className="text-sm text-gray-500">{manageDoc.department}</p>
              </div>
              <button onClick={() => setManageDoc(null)} className="text-gray-400 hover:text-gray-600"><X className="w-6 h-6" /></button>
            </div>

            <div className="p-6 overflow-y-auto grid grid-cols-1 md:grid-cols-2 gap-8">
              
              {/* Weekly Schedule Section */}
              <div className="space-y-4">
                <h4 className="font-semibold text-gray-800 flex items-center gap-2"><Clock className="w-5 h-5 text-blue-600" /> Weekly Hours</h4>
                <form onSubmit={handleAddSchedule} className="flex flex-wrap gap-2 items-end bg-blue-50/50 p-3 rounded-lg border border-blue-100">
                  <div className="flex-1 min-w-[120px]">
                    <label className="block text-xs font-medium text-gray-600 mb-1">Day</label>
                    <select value={schedDay} onChange={e => setSchedDay(e.target.value)} className="w-full text-sm border rounded p-2">
                      {DAYS_OF_WEEK.map((d, i) => <option key={i} value={i}>{d}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Start</label>
                    <input type="time" value={schedStart} onChange={e => setSchedStart(e.target.value)} required className="w-full text-sm border rounded p-2" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">End</label>
                    <input type="time" value={schedEnd} onChange={e => setSchedEnd(e.target.value)} required className="w-full text-sm border rounded p-2" />
                  </div>
                  <button type="submit" className="bg-blue-600 text-white p-2 rounded hover:bg-blue-700"><Plus className="w-5 h-5" /></button>
                </form>

                <div className="space-y-2">
                  {schedules.map(s => (
                    <div key={s.id} className="flex justify-between items-center bg-white border rounded-lg p-3 text-sm">
                      <span className="font-medium w-24">{DAYS_OF_WEEK[s.day_of_week]}</span>
                      <span className="text-gray-600">{s.start_time} - {s.end_time}</span>
                      <button onClick={() => deleteSchedule(s.id)} className="text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  ))}
                  {schedules.length === 0 && <p className="text-sm text-gray-400 italic">No schedules set.</p>}
                </div>
              </div>

              {/* Leaves Section */}
              <div className="space-y-4">
                <h4 className="font-semibold text-gray-800 flex items-center gap-2"><CalendarDays className="w-5 h-5 text-red-600" /> Mark Absence</h4>
                <form onSubmit={handleAddLeave} className="flex flex-wrap gap-2 items-end bg-red-50/50 p-3 rounded-lg border border-red-100">
                  <div className="flex-1 min-w-[120px]">
                    <label className="block text-xs font-medium text-gray-600 mb-1">Date</label>
                    <input type="date" value={leaveDate} onChange={e => setLeaveDate(e.target.value)} required className="w-full text-sm border rounded p-2" />
                  </div>
                  <div className="flex-1 min-w-[120px]">
                    <label className="block text-xs font-medium text-gray-600 mb-1">Reason (Optional)</label>
                    <input type="text" value={leaveReason} onChange={e => setLeaveReason(e.target.value)} placeholder="e.g. Vacation" className="w-full text-sm border rounded p-2" />
                  </div>
                  <button type="submit" className="bg-red-600 text-white p-2 rounded hover:bg-red-700"><Plus className="w-5 h-5" /></button>
                </form>

                <div className="space-y-2">
                  {leaves.map(l => (
                    <div key={l.id} className="flex justify-between items-center bg-white border rounded-lg p-3 text-sm">
                      <span className="font-medium text-red-600">{l.date}</span>
                      <span className="text-gray-600 truncate max-w-[150px]">{l.reason || 'Absent'}</span>
                      <button onClick={() => deleteLeave(l.id)} className="text-gray-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  ))}
                  {leaves.length === 0 && <p className="text-sm text-gray-400 italic">No leaves marked.</p>}
                </div>
              </div>

            </div>
          </div>
        </div>
      )}
    </div>
  );
}
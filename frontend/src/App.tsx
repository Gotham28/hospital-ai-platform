import { Routes, Route, Navigate, Link, useParams } from 'react-router-dom';
import DashboardLayout from './layouts/DashboardLayout';
import CreateHospitalModal from './components/CreateHospitalModal';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import DoctorsPage from './pages/Doctors';
import SettingsPage from './pages/Settings';
import ThemeLoader from './themes/ThemeLoader';
import api from './api/axios';
import { useEffect, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { useAuth } from './context/AuthContext';
import AppointmentsTab from './components/AppointmentsTab';
import PharmacyPage from './pages/Pharmacy';
import LabTestsPage from './pages/LabTests';
import IrisPage from './pages/IrisPage'


/**
 * Replace the HospitalList function in frontend/src/App.tsx with this.
 * 
 * Changes:
 *  - Adds a Delete button (trash icon) on each hospital card
 *  - Shows a confirmation dialog before deleting
 *  - Calls DELETE /hospitals/:id on confirm
 *  - Refreshes the list after deletion
 * 
 * Also add this import at the top of App.tsx:
 *   import { Plus, Trash2 } from 'lucide-react';
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Trash2 } from 'lucide-react';
import api from './api/axios';
import CreateHospitalModal from './components/CreateHospitalModal';

// ── Confirmation dialog ──────────────────────────────────────────
interface DeleteDialogProps {
  hospital: { id: number; name: string } | null;
  onConfirm: () => void;
  onCancel: () => void;
  isDeleting: boolean;
}

function DeleteConfirmDialog({ hospital, onConfirm, onCancel, isDeleting }: DeleteDialogProps) {
  if (!hospital) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full mx-4 p-6">
        <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Trash2 className="w-6 h-6 text-red-600" />
        </div>
        <h3 className="text-lg font-bold text-gray-900 text-center mb-2">Delete Hospital?</h3>
        <p className="text-sm text-gray-500 text-center mb-1">
          You are about to permanently delete
        </p>
        <p className="text-sm font-semibold text-gray-900 text-center mb-4">
          "{hospital.name}"
        </p>
        <p className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2 text-center mb-6">
          ⚠️ This will also delete all doctors, appointments, knowledge base entries,
          and staff accounts for this hospital. This cannot be undone.
        </p>
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isDeleting}
            className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isDeleting ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                Deleting…
              </>
            ) : (
              <>
                <Trash2 className="w-4 h-4" /> Delete Permanently
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── HospitalList ─────────────────────────────────────────────────
function HospitalList() {
  const [hospitals, setHospitals] = useState<any[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const fetchHospitals = () => {
    api.get('/hospitals/')
      .then(res => setHospitals(res.data))
      .catch(console.error);
  };

  useEffect(() => { fetchHospitals(); }, []);

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await api.delete(`/hospitals/${deleteTarget.id}`);
      setDeleteTarget(null);
      fetchHospitals();
    } catch (err: any) {
      setDeleteError(
        err?.response?.data?.detail || 'Failed to delete hospital. Please try again.'
      );
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Hospital Management</h2>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" /> Add Hospital
        </button>
      </div>

      {/* Error banner */}
      {deleteError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex justify-between items-center">
          {deleteError}
          <button onClick={() => setDeleteError(null)} className="text-red-400 hover:text-red-600 ml-4 font-bold">×</button>
        </div>
      )}

      {/* Hospital cards */}
      <div className="grid gap-6 md:grid-cols-3">
        {hospitals.map((h: any) => (
          <div
            key={h.id}
            className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow relative group"
          >
            {/* Delete button — top-right corner, visible on hover */}
            <button
              onClick={() => setDeleteTarget({ id: h.id, name: h.name })}
              title="Delete hospital"
              className="absolute top-3 right-3 p-1.5 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 transition-all opacity-0 group-hover:opacity-100"
            >
              <Trash2 className="w-4 h-4" />
            </button>

            <h3 className="font-bold text-gray-900 text-lg pr-8">{h.name}</h3>
            <p className="text-xs text-gray-400 mb-4">Slug: {h.slug}</p>

            <div className="flex gap-2 border-t pt-4">
              <Link
                to={`/hospitals/${h.id}/appointments`}
                className="flex-1 text-center text-xs bg-emerald-600 text-white py-2 rounded-md font-medium hover:bg-emerald-700"
              >
                Appointments
              </Link>
              <Link
                to={`/hospitals/${h.id}/training`}
                className="flex-1 text-center text-xs bg-blue-600 text-white py-2 rounded-md font-medium hover:bg-blue-700"
              >
                Train AI
              </Link>
              <Link
                to={`/hospitals/${h.id}/settings`}
                className="flex-1 text-center text-xs border border-gray-300 text-gray-600 py-2 rounded-md font-medium hover:bg-gray-50"
              >
                Settings
              </Link>
            </div>
          </div>
        ))}
      </div>

      {/* Modals */}
      <CreateHospitalModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={fetchHospitals}
      />

      <DeleteConfirmDialog
        hospital={deleteTarget}
        onConfirm={handleDeleteConfirm}
        onCancel={() => { setDeleteTarget(null); setDeleteError(null); }}
        isDeleting={isDeleting}
      />
    </div>
  );
}

export default HospitalList;

  useEffect(() => { fetchHospitals(); }, []);

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Hospital Management</h2>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" /> Add Hospital
        </button>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {hospitals.map((h: any) => (
          <div key={h.id} className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
            <h3 className="font-bold text-gray-900 text-lg">{h.name}</h3>
            <p className="text-xs text-gray-400 mb-4">Slug: {h.slug}</p>

            <div className="flex gap-2 border-t pt-4">
              <Link
                to={`/hospitals/${h.id}/appointments`}
                className="flex-1 text-center text-xs bg-emerald-600 text-white py-2 rounded-md font-medium hover:bg-emerald-700"
              >
                Appointments
              </Link>
              <Link
                to={`/hospitals/${h.id}/training`}
                className="flex-1 text-center text-xs bg-blue-600 text-white py-2 rounded-md font-medium hover:bg-blue-700"
              >
                Train AI
              </Link>
              <Link
                to={`/hospitals/${h.id}/settings`}
                className="flex-1 text-center text-xs border border-gray-300 text-gray-600 py-2 rounded-md font-medium hover:bg-gray-50"
              >
                Settings
              </Link>
            </div>
          </div>
        ))}
      </div>

      <CreateHospitalModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={fetchHospitals}
      />
    </div>
  );
}

// ==========================================
// NEW: Security Guard Component
// ==========================================
function StaffGuard({ children }: { children: React.ReactNode }) {
  const { role, hospitalId } = useAuth();
  const { hospitalId: routeHospitalId } = useParams();

  // If staff tries to access a different hospital's URL, kick them back to their own
  if (role === 'staff' && String(hospitalId) !== String(routeHospitalId)) {
    return <Navigate to={`/hospitals/${hospitalId}/appointments`} replace />;

  }
  
  return <>{children}</>;
}

// ==========================================
// MAIN APP ROUTER
// ==========================================
export default function App() {
  const { isAuthenticated, role, hospitalId } = useAuth();

  return (
    <Routes>
      {/* Public patient-facing route */}
{/* Iris Hospital dedicated route - must be before /p/:hospitalSlug */}


{/* Public patient-facing route */}
<Route path="/p/:hospitalSlug" element={<ThemeLoader />} />
<Route path="/iris" element={<IrisPage />} />

{/* Auth route */}
<Route
  path="/login"
  element={isAuthenticated ? <Navigate to="/" replace /> : <Login />}
/>


      {/* Protected admin routes */}
      <Route element={isAuthenticated ? <DashboardLayout /> : <Navigate to="/login" replace />}>
        
        {/* Root Route: Redirect Staff directly to Settings, Show list to Superadmin */}
        <Route 
          path="/" 
          element={
            role === 'staff' && hospitalId ? (
              <Navigate to={`/hospitals/${hospitalId}/appointments`} replace />

            ) : (
              <HospitalList />
            )
          } 
        />

        {/* Common Routes (Secured by StaffGuard so they can't swap IDs) */}
        <Route 
          path="/hospitals/:hospitalId/appointments" 
          element={<StaffGuard><AppointmentsTab /></StaffGuard>} 
        />
        <Route 
          path="/hospitals/:hospitalId/doctors" 
          element={<StaffGuard><DoctorsPage /></StaffGuard>} 
        />
        <Route 
          path="/hospitals/:hospitalId/settings" 
          element={<StaffGuard><SettingsPage /></StaffGuard>} 
        />
        <Route 
          path="/hospitals/:hospitalId/pharmacy" 
          element={<StaffGuard><PharmacyPage /></StaffGuard>} 
        />
        <Route 
          path="/hospitals/:hospitalId/lab-tests" 
          element={<StaffGuard><LabTestsPage /></StaffGuard>} 
        />

        {/* Superadmin Only Routes */}
        <Route 
          path="/hospitals/:hospitalId/training" 
          element={role === 'superadmin' ? <Dashboard /> : <Navigate to="/" replace />} 
        />

      </Route>

      {/* Catch-all redirects to root, which will cleanly re-route based on role */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
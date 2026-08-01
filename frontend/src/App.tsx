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
import IrisPage from './pages/IrisPage';
import MessagingPage from './pages/Messaging';

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 backdrop-blur-[2px]">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-md w-full mx-4 overflow-hidden">
        <div className="px-6 pt-6 pb-4 border-b border-slate-100">
          <div className="w-10 h-10 bg-rose-50 rounded-full flex items-center justify-center mb-4">
            <Trash2 className="w-5 h-5 text-rose-500" />
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-1">Delete Hospital?</h3>
          <p className="text-sm text-slate-500">
            You are about to permanently delete <span className="font-semibold text-slate-900">"{hospital.name}"</span>
          </p>
        </div>
        
        <div className="px-6 py-4">
          <p className="text-xs text-rose-600 bg-rose-50 border border-rose-100 rounded-lg px-3 py-2">
            ⚠️ This will also delete all doctors, appointments, knowledge base entries,
            and staff accounts for this hospital. This cannot be undone.
          </p>
        </div>

        <div className="px-6 pb-6 pt-2 flex gap-3 justify-end">
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className="px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 hover:border-slate-300 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isDeleting}
            className="px-4 py-2 bg-rose-500 text-white rounded-lg text-sm font-medium hover:bg-rose-600 transition-colors disabled:opacity-50 flex items-center gap-2"
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
              'Delete Permanently'
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

  // Assign distinct colors based on index to give the list variety
  const getAvatarColors = (id: number) => {
    const variants = [
      'bg-indigo-50 text-indigo-600',
      'bg-violet-50 text-violet-600',
      'bg-cyan-50 text-cyan-600',
      'bg-amber-50 text-amber-600'
    ];
    return variants[id % variants.length];
  };

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-2xl font-bold text-slate-900">Hospital Management</h2>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500/30 transition-colors"
        >
          <Plus className="w-4 h-4" /> Add Hospital
        </button>
      </div>

      {/* Error banner */}
      {deleteError && (
        <div className="mb-6 px-4 py-3 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-700 flex justify-between items-center">
          {deleteError}
          <button onClick={() => setDeleteError(null)} className="text-rose-400 hover:text-rose-600 ml-4 font-bold">×</button>
        </div>
      )}

      {/* Hospital cards */}
      <div className="grid gap-5 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
        {hospitals.map((h: any) => (
          <div
            key={h.id}
            className="bg-white rounded-xl border border-slate-200 hover:border-slate-300 transition-all duration-150 relative group overflow-hidden"
          >
            {/* Delete button — top-right, appears on hover */}
            <button
              onClick={() => setDeleteTarget({ id: h.id, name: h.name })}
              title="Delete hospital"
              className="absolute top-3 right-3 p-1.5 rounded-md text-slate-300 hover:text-rose-500 hover:bg-rose-50 transition-all opacity-0 group-hover:opacity-100 focus:opacity-100"
            >
              <Trash2 className="w-4 h-4" />
            </button>

            <div className="px-5 py-5">
              <div className="flex items-start gap-3 mb-4">
                {/* Hospital initial avatar */}
                <div className={`w-9 h-9 rounded-lg flex items-center justify-center font-bold text-sm flex-shrink-0 ${getAvatarColors(h.id)}`}>
                  {h.name[0]}
                </div>
                <div className="min-w-0 pr-6">
                  <h3 className="font-semibold text-slate-900 text-sm truncate">{h.name}</h3>
                  <p className="text-[11px] text-slate-400 mt-0.5 font-mono truncate">{h.slug}</p>
                </div>
              </div>
            </div>

            <div className="px-5 pb-5 flex gap-2 border-t border-slate-100 pt-4">
              <Link
                to={`/hospitals/${h.id}/appointments`}
                className="flex-1 text-center text-[12px] font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 py-1.5 rounded-md transition-colors"
              >
                Appointments
              </Link>
              <Link
                to={`/hospitals/${h.id}/training`}
                className="flex-1 text-center text-[12px] font-medium text-cyan-700 bg-cyan-50 hover:bg-cyan-100 py-1.5 rounded-md transition-colors"
              >
                Train AI
              </Link>
              <Link
                to={`/hospitals/${h.id}/settings`}
                className="flex-1 text-center text-[12px] font-medium text-slate-600 hover:text-slate-700 hover:bg-slate-50 py-1.5 rounded-md transition-colors border border-slate-200"
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
        <Route 
          path="/hospitals/:hospitalId/messaging" 
          element={<StaffGuard><MessagingPage /></StaffGuard>} 
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
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
import { Plus } from 'lucide-react';
import { useAuth } from './context/AuthContext';
import AppointmentsTab from './components/AppointmentsTab';
import PharmacyPage from './pages/Pharmacy';
import LabTestsPage from './pages/LabTests';

function HospitalList() {
  const [hospitals, setHospitals] = useState<any[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchHospitals = () => {
    api.get('/hospitals/')
      .then(res => setHospitals(res.data))
      .catch(console.error);
  };

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
      <Route path="/p/:hospitalSlug" element={<ThemeLoader />} />

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
import { Routes, Route, Navigate, Link } from 'react-router-dom';
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

export default function App() {
  // FIX: Read from AuthContext (useState) instead of localStorage directly.
  // The old code was: const isAuthenticated = !!localStorage.getItem('token')
  // That's a plain const evaluated once at render time and never updated,
  // so after login() set the token, App still saw isAuthenticated=false
  // until a full page reload forced a re-evaluation. Using the context
  // state means any call to login() or logout() triggers a re-render here
  // automatically, with no reload required.
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      {/* Public patient-facing route */}
      <Route path="/p/:hospitalSlug" element={<ThemeLoader />} />
      <Route path="/hospitals/:hospitalId/appointments" element={<AppointmentsTab hospitalId={...} />} />

      {/* Auth route — redirect to / if already logged in */}
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <Login />}
      />

      {/* Protected admin routes */}
      <Route element={isAuthenticated ? <DashboardLayout /> : <Navigate to="/login" replace />}>
        <Route path="/" element={<HospitalList />} />
        <Route path="/hospitals/:hospitalId/doctors" element={<DoctorsPage />} />
        <Route path="/hospitals/:hospitalId/training" element={<Dashboard />} />
        <Route path="/hospitals/:hospitalId/settings" element={<SettingsPage />} />
      </Route>

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
import { Outlet, Link, useNavigate, useParams, useLocation } from 'react-router-dom';
import { LayoutDashboard, Users, Building2, Settings, LogOut, BrainCircuit, CalendarCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function DashboardLayout() {
  const navigate = useNavigate();
  const { hospitalId } = useParams();
  const location = useLocation();
  const { logout, role } = useAuth(); // Cleanly destructured together

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path: string) => location.pathname === path;
  const linkBase = 'flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors';
  const linkActive = 'bg-blue-50 text-blue-600';
  const linkIdle = 'text-gray-700 hover:bg-blue-50';

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col shadow-sm">
        <div className="p-6 border-b">
          <h2 className="text-xl font-bold text-blue-600 flex items-center gap-2">
            <Building2 className="w-6 h-6" /> Corvus Labs
          </h2>
        </div>

        <nav className="flex-1 p-4 space-y-2">
          {/* Hospitals — Superadmin only */}
          {role === 'superadmin' && (
            <Link
              to="/"
              className={`${linkBase} ${isActive('/') ? linkActive : linkIdle}`}
            >
              <LayoutDashboard className="w-5 h-5" /> Hospitals
            </Link>
          )}

          {hospitalId && (
            <>
              <div className="mt-6 mb-2 px-4 text-[10px] font-bold text-gray-400 uppercase tracking-widest">
                Management
              </div>

              {/* Appointments — visible to all roles */}
              <Link
                to={`/hospitals/${hospitalId}/appointments`}
                className={`${linkBase} ${isActive(`/hospitals/${hospitalId}/appointments`) ? linkActive : linkIdle}`}
              >
                <CalendarCheck className="w-5 h-5 text-blue-500" /> Appointments
              </Link>

              {/* Doctors — visible to all roles */}
              <Link
                to={`/hospitals/${hospitalId}/doctors`}
                className={`${linkBase} ${isActive(`/hospitals/${hospitalId}/doctors`) ? linkActive : linkIdle}`}
              >
                <Users className="w-5 h-5 text-blue-500" /> Doctors
              </Link>

              {/* Superadmin only below */}
              {role === 'superadmin' && (
                <>
                  <Link
                    to={`/hospitals/${hospitalId}/training`}
                    className={`${linkBase} ${isActive(`/hospitals/${hospitalId}/training`) ? linkActive : linkIdle}`}
                  >
                    <BrainCircuit className="w-5 h-5 text-blue-500" /> AI Training
                  </Link>

                  <Link
                    to={`/hospitals/${hospitalId}/settings`}
                    className={`${linkBase} ${isActive(`/hospitals/${hospitalId}/settings`) ? linkActive : linkIdle}`}
                  >
                    <Settings className="w-5 h-5 text-blue-500" /> Settings
                  </Link>
                </>
              )}
            </>
          )}
        </nav>

        <div className="p-4 border-t">
          <button
            onClick={handleSignOut}
            className="flex items-center gap-3 px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg text-sm font-medium w-full transition-colors"
          >
            <LogOut className="w-5 h-5" /> Sign Out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto bg-gray-50">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
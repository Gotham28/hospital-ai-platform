import { Outlet, Link, useNavigate, useParams, useLocation } from 'react-router-dom';
import { LayoutDashboard, Users, Building2, Settings, LogOut, BrainCircuit, CalendarCheck, Pill, TestTube, MessageSquare } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import GothosByline from '../components/common/GothosByline';

export default function DashboardLayout() {
  const navigate = useNavigate();
  const { hospitalId } = useParams();
  const location = useLocation();
  const { logout, role } = useAuth();

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path: string) => location.pathname === path;

  const focusRing = 'focus-visible:outline-[3px] focus-visible:outline-solid focus-visible:outline-gothos-focus focus-visible:outline-offset-3';
  const linkBase = `flex items-center gap-3 px-3 py-2.5 rounded-gothos-bubble text-sm font-medium transition-colors duration-[250ms] motion-reduce:transition-none ${focusRing}`;
  const linkState = (active: boolean) =>
    active ? 'bg-gothos-sage text-gothos-forest' : 'text-gothos-muted hover:bg-gothos-mist';
  const sectionLabel = 'mt-8 mb-4 px-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-gothos-emerald-text';

  return (
    <div className="flex h-screen bg-gothos-bg admin-shell font-gothos text-gothos-ink">
      {/* Light sidebar */}
      <aside className="w-[260px] flex flex-col bg-white border-r border-gothos-line-soft shadow-[0_30px_80px_rgba(30,91,63,.12)] z-10">
        <div className="p-6 border-b border-gothos-line-soft flex flex-col justify-center gap-1">
          <h2 className="text-xl font-bold tracking-[-0.03em] text-gothos-forest flex items-center gap-2">
            AROGYA
          </h2>
          <GothosByline />
        </div>

        <nav className="flex-1 p-4 space-y-1.5 overflow-y-auto">
          {role === 'superadmin' && (
            <Link
              to="/"
              className={`${linkBase} ${linkState(isActive('/'))}`}
            >
              <LayoutDashboard className="w-5 h-5" /> Hospitals
            </Link>
          )}

          {hospitalId && (
            <>
              <div className={sectionLabel}>
                Management
              </div>

              <Link
                to={`/hospitals/${hospitalId}/appointments`}
                className={`${linkBase} ${linkState(isActive(`/hospitals/${hospitalId}/appointments`))}`}
              >
                <CalendarCheck className="w-5 h-5" /> Appointments
              </Link>

              <Link
                to={`/hospitals/${hospitalId}/doctors`}
                className={`${linkBase} ${linkState(isActive(`/hospitals/${hospitalId}/doctors`))}`}
              >
                <Users className="w-5 h-5" /> Doctors
              </Link>

              <Link
                to={`/hospitals/${hospitalId}/pharmacy`}
                className={`${linkBase} ${linkState(isActive(`/hospitals/${hospitalId}/pharmacy`))}`}
              >
                <Pill className="w-5 h-5" /> Pharmacy
              </Link>

              <Link
                to={`/hospitals/${hospitalId}/lab-tests`}
                className={`${linkBase} ${linkState(isActive(`/hospitals/${hospitalId}/lab-tests`))}`}
              >
                <TestTube className="w-5 h-5" /> Lab Tests
              </Link>

              <Link
                to={`/hospitals/${hospitalId}/messaging`}
                className={`${linkBase} ${linkState(isActive(`/hospitals/${hospitalId}/messaging`))}`}
              >
                <MessageSquare className="w-5 h-5" /> Messaging
              </Link>

              <Link
                to={`/hospitals/${hospitalId}/settings`}
                className={`${linkBase} ${linkState(isActive(`/hospitals/${hospitalId}/settings`))}`}
              >
                <Settings className="w-5 h-5" /> Settings
              </Link>

              {role === 'superadmin' && (
                <>
                  <div className={sectionLabel}>
                    Platform Admin
                  </div>
                  <Link
                    to={`/hospitals/${hospitalId}/training`}
                    className={`${linkBase} ${linkState(isActive(`/hospitals/${hospitalId}/training`))}`}
                  >
                    <BrainCircuit className="w-5 h-5" /> AI Training
                  </Link>
                </>
              )}
            </>
          )}
        </nav>

        <div className="p-4 border-t border-gothos-line-soft">
          <button
            onClick={handleSignOut}
            className={`flex items-center gap-3 px-3 py-2 text-gothos-muted hover:text-rose-600 hover:bg-rose-500/10 rounded-gothos-bubble text-sm font-medium w-full transition-colors duration-[250ms] motion-reduce:transition-none ${focusRing}`}
          >
            <LogOut className="w-5 h-5" /> Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto bg-gothos-bg relative">
        <div className="max-w-7xl mx-auto px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

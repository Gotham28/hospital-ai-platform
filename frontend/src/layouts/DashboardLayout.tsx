import { Outlet, Link, useNavigate, useParams, useLocation } from 'react-router-dom';
import { LayoutDashboard, Users, Building2, Settings, LogOut, BrainCircuit, CalendarCheck, Pill, TestTube, MessageSquare } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

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
  
  const linkBase = 'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200';
  
  return (
    <div className="flex h-screen bg-slate-50 admin-shell font-sans text-slate-900">
      {/* Dark Sidebar with gradient */}
      <aside 
        className="w-[260px] flex flex-col shadow-xl z-10"
        style={{ background: 'linear-gradient(180deg, #0f2318 0%, #081410 100%)' }}
      >
        <div className="p-6 border-b border-white/10 flex flex-col justify-center">
          <h2 className="text-xl font-extrabold text-white flex items-center gap-2">
            AROGYA
          </h2>
          <span className="text-xs text-brand-400 font-medium mt-1 uppercase tracking-wider">by Gothos Labs</span>
        </div>

        <nav className="flex-1 p-4 space-y-1.5 overflow-y-auto">
          {role === 'superadmin' && (
            <Link
              to="/"
              className={`${linkBase} ${isActive('/') ? 'bg-brand-500/15 text-brand-300' : 'text-white/70 hover:bg-white/5 hover:text-white'}`}
            >
              <LayoutDashboard className={`w-5 h-5 ${isActive('/') ? 'text-brand-400' : 'text-brand-500/70'}`} /> Hospitals
            </Link>
          )}

          {hospitalId && (
            <>
              <div className="mt-8 mb-4 px-3 text-[10px] font-bold text-white/40 uppercase tracking-widest">
                Management
              </div>

              <Link
                to={`/hospitals/${hospitalId}/appointments`}
                className={`${linkBase} ${isActive(`/hospitals/${hospitalId}/appointments`) ? 'bg-indigo-500/15 text-indigo-300' : 'text-white/70 hover:bg-white/5 hover:text-white'}`}
              >
                <CalendarCheck className={`w-5 h-5 ${isActive(`/hospitals/${hospitalId}/appointments`) ? 'text-indigo-400' : 'text-indigo-400/60'}`} /> Appointments
              </Link>

              <Link
                to={`/hospitals/${hospitalId}/doctors`}
                className={`${linkBase} ${isActive(`/hospitals/${hospitalId}/doctors`) ? 'bg-violet-500/15 text-violet-300' : 'text-white/70 hover:bg-white/5 hover:text-white'}`}
              >
                <Users className={`w-5 h-5 ${isActive(`/hospitals/${hospitalId}/doctors`) ? 'text-violet-400' : 'text-violet-400/60'}`} /> Doctors
              </Link>

              <Link
                to={`/hospitals/${hospitalId}/pharmacy`}
                className={`${linkBase} ${isActive(`/hospitals/${hospitalId}/pharmacy`) ? 'bg-brand-500/15 text-brand-300' : 'text-white/70 hover:bg-white/5 hover:text-white'}`}
              >
                <Pill className={`w-5 h-5 ${isActive(`/hospitals/${hospitalId}/pharmacy`) ? 'text-brand-400' : 'text-brand-400/60'}`} /> Pharmacy
              </Link>

              <Link
                to={`/hospitals/${hospitalId}/lab-tests`}
                className={`${linkBase} ${isActive(`/hospitals/${hospitalId}/lab-tests`) ? 'bg-cyan-500/15 text-cyan-300' : 'text-white/70 hover:bg-white/5 hover:text-white'}`}
              >
                <TestTube className={`w-5 h-5 ${isActive(`/hospitals/${hospitalId}/lab-tests`) ? 'text-cyan-400' : 'text-cyan-400/60'}`} /> Lab Tests
              </Link>

              <Link
                to={`/hospitals/${hospitalId}/messaging`}
                className={`${linkBase} ${isActive(`/hospitals/${hospitalId}/messaging`) ? 'bg-indigo-500/15 text-indigo-300' : 'text-white/70 hover:bg-white/5 hover:text-white'}`}
              >
                <MessageSquare className={`w-5 h-5 ${isActive(`/hospitals/${hospitalId}/messaging`) ? 'text-indigo-400' : 'text-indigo-400/60'}`} /> Messaging
              </Link>

              <Link
                to={`/hospitals/${hospitalId}/settings`}
                className={`${linkBase} ${isActive(`/hospitals/${hospitalId}/settings`) ? 'bg-white/10 text-white' : 'text-white/70 hover:bg-white/5 hover:text-white'}`}
              >
                <Settings className={`w-5 h-5 ${isActive(`/hospitals/${hospitalId}/settings`) ? 'text-slate-300' : 'text-slate-400/60'}`} /> Settings
              </Link>

              {role === 'superadmin' && (
                <>
                  <div className="mt-8 mb-4 px-3 text-[10px] font-bold text-white/40 uppercase tracking-widest">
                    Platform Admin
                  </div>
                  <Link
                    to={`/hospitals/${hospitalId}/training`}
                    className={`${linkBase} ${isActive(`/hospitals/${hospitalId}/training`) ? 'bg-cyan-500/15 text-cyan-300' : 'text-white/70 hover:bg-white/5 hover:text-white'}`}
                  >
                    <BrainCircuit className={`w-5 h-5 ${isActive(`/hospitals/${hospitalId}/training`) ? 'text-cyan-400' : 'text-cyan-400/60'}`} /> AI Training
                  </Link>
                </>
              )}
            </>
          )}
        </nav>

        <div className="p-4 border-t border-white/10">
          <button
            onClick={handleSignOut}
            className="flex items-center gap-3 px-3 py-2 text-white/50 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg text-sm font-medium w-full transition-colors"
          >
            <LogOut className="w-5 h-5" /> Sign Out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto bg-slate-50 relative">
        <div className="max-w-7xl mx-auto px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
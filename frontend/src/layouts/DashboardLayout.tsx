import { Outlet, Link, useNavigate, useParams } from 'react-router-dom';
import { LayoutDashboard, Users, Building2, Settings, LogOut, BrainCircuit } from 'lucide-react';

export default function DashboardLayout() {
  const navigate = useNavigate();
  // 1. Grab the hospitalId from the URL so the links stay dynamic
  const { hospitalId } = useParams();

  const handleSignOut = () => {
    localStorage.removeItem('token');
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col shadow-sm">
        <div className="p-6 border-b">
          <h2 className="text-xl font-bold text-blue-600 flex items-center gap-2">
            <Building2 className="w-6 h-6" /> Corvus Labs
          </h2>
        </div>

        <nav className="flex-1 p-4 space-y-2">
          {/* Main Hospital List (Reset context) */}
          <Link to="/" className="flex items-center gap-3 px-4 py-3 text-gray-700 hover:bg-blue-50 rounded-lg text-sm font-medium transition-colors">
            <LayoutDashboard className="w-5 h-5" /> Hospitals
          </Link>

          {/* 2. Dynamic Links: Only show if a Hospital is selected */}
          {hospitalId && (
            <>
              <div className="mt-6 mb-2 px-4 text-[10px] font-bold text-gray-400 uppercase tracking-widest">
                Management
              </div>
              
              <Link 
                to={`/hospitals/${hospitalId}/training`} 
                className="flex items-center gap-3 px-4 py-3 text-gray-700 hover:bg-blue-50 rounded-lg text-sm font-medium transition-colors"
              >
                <BrainCircuit className="w-5 h-5 text-blue-500" /> AI Training
              </Link>

              <Link 
                to={`/hospitals/${hospitalId}/doctors`} 
                className="flex items-center gap-3 px-4 py-3 text-gray-700 hover:bg-blue-50 rounded-lg text-sm font-medium transition-colors"
              >
                <Users className="w-5 h-5 text-blue-500" /> Doctors
              </Link>

              <Link 
                to={`/hospitals/${hospitalId}/settings`} 
                className="flex items-center gap-3 px-4 py-3 text-gray-700 hover:bg-blue-50 rounded-lg text-sm font-medium transition-colors"
              >
                <Settings className="w-5 h-5 text-blue-500" /> Settings
              </Link>
            </>
          )}
        </nav>

        <div className="p-4 border-t">
          <button onClick={handleSignOut} className="flex items-center gap-3 px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg text-sm font-medium w-full transition-colors">
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
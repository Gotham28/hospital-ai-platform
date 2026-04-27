import { useEffect, useState } from 'react';
import api from '../api/axios';
import { Activity, CreditCard, TrendingUp, RefreshCw } from 'lucide-react';

export default function HospitalStats({ hospitalId }: { hospitalId: number }) {
  const [billing, setBilling] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);

  const fetchBilling = async () => {
    try {
      const res = await api.get(`/hospitals/${hospitalId}/billing`);
      setBilling(res.data);
      setError(null);
    } catch (err) {
      setError("Could not load billing data.");
    }
  };

  useEffect(() => {
    if (hospitalId) fetchBilling();
  }, [hospitalId]);

  const handleReset = async () => {
    if (!confirm("Are you sure you want to reset all usage data for this billing cycle?")) return;
    setResetting(true);
    try {
      await api.delete(`/hospitals/${hospitalId}/billing/reset`);
      await fetchBilling();
    } catch (err) {
      alert("Failed to reset billing.");
    } finally {
      setResetting(false);
    }
  };

  if (!billing && !error) return <div className="p-8 text-center animate-pulse">Calculating usage...</div>;

  return (
    <div className="relative">
      <div className="absolute -top-12 right-0">
         <button 
           onClick={handleReset} 
           disabled={resetting}
           className="flex items-center gap-2 text-sm text-gray-500 hover:text-red-600 transition-colors"
         >
           <RefreshCw className={`w-4 h-4 ${resetting ? 'animate-spin' : ''}`} />
           Reset Billing Cycle
         </button>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {/* Activity Card */}
        <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
          <div className="flex items-center gap-3 text-blue-600 mb-4">
            <Activity size={20} />
            <h4 className="font-semibold text-gray-700">Monthly Usage</h4>
          </div>
          <div className="space-y-1">
            <p className="text-2xl font-bold text-gray-900">{billing?.usage?.total_chats ?? 0}</p>
            <p className="text-xs text-gray-400 font-medium uppercase">{(billing?.usage?.tokens_consumed ?? 0).toLocaleString()} tokens</p>
          </div>
        </div>

        {/* Cost Card */}
        <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
          <div className="flex items-center gap-3 text-orange-600 mb-4">
            <TrendingUp size={20} />
            <h4 className="font-semibold text-gray-700">OpenAI Overhead</h4>
          </div>
          <div className="space-y-1">
             {/* Changed to Rupees */}
            <p className="text-2xl font-bold text-gray-900">₹{(billing?.usage?.raw_cost_usd * 83).toFixed(2) ?? "0.00"}</p>
            <p className="text-xs text-gray-400 font-medium uppercase">Raw API Cost</p>
          </div>
        </div>

        {/* Invoice Card */}
        <div className="bg-blue-600 p-6 rounded-xl shadow-lg text-white">
          <div className="flex items-center gap-3 mb-4 opacity-90">
            <CreditCard size={20} />
            <h4 className="font-semibold">Current Invoice</h4>
          </div>
          <div className="space-y-1">
            <p className="text-3xl font-bold">₹{(billing?.invoice?.total_due_inr ?? 0).toLocaleString()}</p>
            <p className="text-xs opacity-75 font-medium uppercase">Platform: ₹{billing?.invoice?.platform_fee ?? 0} + Usage</p>
          </div>
        </div>
      </div>
    </div>
  );
}
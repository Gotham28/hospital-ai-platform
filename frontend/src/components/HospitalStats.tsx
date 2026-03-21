import { useEffect, useState } from 'react';
import api from '../api/axios';
import { Activity, CreditCard, TrendingUp } from 'lucide-react';

export default function HospitalStats({ hospitalId }: { hospitalId: number }) {
  const [billing, setBilling] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchBilling = async () => {
      try {
        const res = await api.get(`/hospitals/${hospitalId}/billing`);
        setBilling(res.data);
        setError(null);
      } catch (err) {
        console.error("Billing fetch failed", err);
        setError("Could not load billing data.");
      }
    };
    if (hospitalId) fetchBilling();
  }, [hospitalId]);

  if (!billing && !error) {
    return (
      <div className="p-8 text-center animate-pulse bg-gray-50 rounded-xl border-2 border-dashed border-gray-200">
        <p className="text-gray-500 font-medium">Calculating real-time usage...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 text-red-600 rounded-lg border border-red-100">
        {error}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      {/* Activity Card */}
      <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
        <div className="flex items-center gap-3 text-blue-600 mb-4">
          <Activity size={20} />
          <h4 className="font-semibold text-gray-700">Monthly Usage</h4>
        </div>
        <div className="space-y-1">
          <p className="text-2xl font-bold text-gray-900">
            {billing?.usage?.total_chats ?? 0}
          </p>
          <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">
            {(billing?.usage?.tokens_consumed ?? 0).toLocaleString()} tokens used
          </p>
        </div>
      </div>

      {/* Internal Cost Card */}
      <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
        <div className="flex items-center gap-3 text-orange-600 mb-4">
          <TrendingUp size={20} />
          <h4 className="font-semibold text-gray-700">Gothos Cost (USD)</h4>
        </div>
        <div className="space-y-1">
          <p className="text-2xl font-bold text-gray-900">
            ${billing?.usage?.raw_cost_usd ?? "0.00"}
          </p>
          <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">
            Total OpenAI Overhead
          </p>
        </div>
      </div>

      {/* Invoice Card (INR) */}
      {/* FIX #5: Was reading billing?.invoice?.total_due_inr but the old backend
          returned estimated_invoice_inr at the top level. Backend is now fixed to
          return { invoice: { total_due_inr, platform_fee } } so this path is correct. */}
      <div className="bg-blue-600 p-6 rounded-xl shadow-lg text-white transform hover:scale-[1.02] transition-transform">
        <div className="flex items-center gap-3 mb-4 opacity-90">
          <CreditCard size={20} />
          <h4 className="font-semibold">Current Invoice</h4>
        </div>
        <div className="space-y-1">
          <p className="text-3xl font-bold">
            ₹{(billing?.invoice?.total_due_inr ?? 0).toLocaleString()}
          </p>
          <p className="text-xs opacity-75 font-medium uppercase tracking-wider">
            Platform: ₹{billing?.invoice?.platform_fee ?? 0} + Usage
          </p>
        </div>
      </div>
    </div>
  );
}
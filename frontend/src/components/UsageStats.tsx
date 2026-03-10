import React, { useEffect, useState } from 'react';
import api from '../api/axios';

const UsageStats = () => {
  const [stats, setStats] = useState({ total_tokens: 0, estimated_cost: 0 });

  useEffect(() => {
    // We'll need to create this GET /usage/summary endpoint next
    api.get('/usage/summary')
      .then(res => setStats(res.data))
      .catch(console.error);
  }, []);

  return (
    <div className="p-6 bg-white rounded-xl shadow border border-gray-100">
      <h3 className="text-lg font-bold text-gray-800 mb-4">Billing & Usage</h3>
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-blue-50 p-4 rounded-lg">
          <p className="text-xs text-blue-600 uppercase font-bold">Total Tokens</p>
          <p className="text-2xl font-mono">{stats.total_tokens.toLocaleString()}</p>
        </div>
        <div className="bg-green-50 p-4 rounded-lg">
          <p className="text-xs text-green-600 uppercase font-bold">Estimated Cost</p>
          <p className="text-2xl font-mono">${stats.estimated_cost.toFixed(4)}</p>
        </div>
      </div>
    </div>
  );
};

export default UsageStats;
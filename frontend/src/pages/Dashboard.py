import React, { useEffect, useState } from 'react';
import api from '../api/axios';

const Dashboard = () => {
  const [hospitalName, setHospitalName] = useState('Loading...');

  useEffect(() => {
    // Basic test to see if the "Magic Key" works
    api.get('/hospitals/me')
      .then(res => setHospitalName(res.data.name))
      .catch(() => setHospitalName('Arogya Specialty Hospital'));
  }, []);

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold text-gray-800">Welcome to the Portal</h1>
      <p className="mt-2 text-gray-600">Managing: {hospitalName}</p>
      
      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="p-6 bg-blue-50 rounded-xl border border-blue-100">
          <h3 className="font-bold text-blue-800">AI Status</h3>
          <p className="text-sm text-blue-600">Arogya is online and ready.</p>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
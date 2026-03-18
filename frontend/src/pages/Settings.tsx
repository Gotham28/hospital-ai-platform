import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom'; 
import api from '../api/axios';
import { Save } from 'lucide-react';
// 1. IMPORT the component here
import HospitalStats from '../components/HospitalStats'; 

const Settings = () => {
  const { hospitalId } = useParams(); 
  
  const [settings, setSettings] = useState({ 
    name: '', 
    address: '', 
    system_prompt: '', 
    google_sheet_id: '' 
  });

  useEffect(() => {
    api.get(`/hospitals/${hospitalId}`)
      .then(res => setSettings(res.data))
      .catch(err => console.error("Could not load hospital settings", err));
  }, [hospitalId]);

  const handleSave = async () => {
    try {
      await api.patch(`/hospitals/${hospitalId}`, settings);
      alert("Settings updated successfully!");
    } catch (err) {
      alert("Failed to update settings.");
    }
  };

  return (
    <div className="p-8 max-w-4xl space-y-8">
      <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-100">
        <h2 className="text-2xl font-bold text-gray-800 mb-6">Hospital Configuration</h2>

        {/* 2. PLACED STATS AT THE TOP */}
        <div className="mb-8 border-b pb-8">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Current Usage & Billing</h3>
          {/* Note: We use Number(hospitalId) to match the prop type */}
          <HospitalStats hospitalId={Number(hospitalId)} /> 
        </div>

        <div className="grid gap-6">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Hospital Name</label>
            <input 
              className="w-full p-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" 
              value={settings.name} 
              onChange={(e) => setSettings({...settings, name: e.target.value})}
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Google Sheet ID (Live Availability)</label>
            <input 
              className="w-full p-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono text-sm" 
              placeholder="e.g. 1aBCdEfgHijkLmNoPqRsTuVwXyZ"
              value={settings.google_sheet_id || ''} 
              onChange={(e) => setSettings({...settings, google_sheet_id: e.target.value})}
            />
            <p className="text-xs text-gray-400 mt-2">
              Tip: Share your sheet with: <span className="text-blue-600 font-medium">arogya-bot@arogya-483613.iam.gserviceaccount.com</span>
            </p>
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">AI System Prompt</label>
            <textarea 
              className="w-full p-3 border border-gray-200 rounded-lg h-32 focus:ring-2 focus:ring-blue-500 outline-none" 
              value={settings.system_prompt} 
              onChange={(e) => setSettings({...settings, system_prompt: e.target.value})}
            />
          </div>
        </div>

        <div className="mt-8">
          <button 
            onClick={handleSave} 
            className="flex items-center gap-2 bg-blue-600 text-white px-8 py-3 rounded-lg hover:bg-blue-700 font-bold transition-all shadow-md active:scale-95"
          >
            <Save className="w-5 h-5" /> Save Configuration
          </button>
        </div>
      </div>
    </div>
  );
};

export default Settings;
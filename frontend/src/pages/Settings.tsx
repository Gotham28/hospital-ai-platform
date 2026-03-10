import React, { useEffect, useState } from 'react';
import api from '../api/axios';
import { Save } from 'lucide-react';
import { useParams } from 'react-router-dom'; // Ensure this is imported

const Settings = () => {
  // 1. Get the ID from the URL
  const { hospitalId } = useParams(); 
  
  const [settings, setSettings] = useState({ 
    name: '', 
    address: '', 
    system_prompt: '', 
    google_sheet_id: '' 
  });

  useEffect(() => {
    // 2. Fetch specific hospital data instead of '/me'
    api.get(`/hospitals/${hospitalId}`)
      .then(res => setSettings(res.data))
      .catch(err => console.error("Could not load hospital settings", err));
  }, [hospitalId]);

  const handleSave = async () => {
    try {
      // 3. Update specific hospital data
      await api.patch(`/hospitals/${hospitalId}`, settings);
      alert("Settings updated successfully!");
    } catch (err) {
      alert("Failed to update settings.");
    }
  };

  return (
    <div className="p-8 max-w-3xl space-y-8 bg-white rounded-xl shadow-sm border border-gray-100">
      <h2 className="text-2xl font-bold text-gray-800">Hospital Configuration</h2>
      
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

      <button 
        onClick={handleSave} 
        className="flex items-center gap-2 bg-blue-600 text-white px-8 py-3 rounded-lg hover:bg-blue-700 font-bold transition-all shadow-md active:scale-95"
      >
        <Save className="w-5 h-5" /> Save Configuration
      </button>
    </div>
  );
};

export default Settings;
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom'; 
import api from '../api/axios';
import KnowledgeBaseUpload from './KnowledgeBase'; 
import ChatPreview from '../components/ChatPreview'; 
import HospitalStats from '../components/HospitalStats'; 

const Dashboard = () => {
  const { hospitalId } = useParams(); 
  const navigate = useNavigate();
  const [hospital, setHospital] = useState(null);
  const [loading, setLoading] = useState(true);

  // NEW: state for welcome message + disclaimer — declared with the other hooks, at top level
  const [welcomeMessage, setWelcomeMessage] = useState('');
  const [postBookingDisclaimer, setPostBookingDisclaimer] = useState('');
  const [savingConfig, setSavingConfig] = useState(false);

  useEffect(() => {
    if (!hospitalId) {
      navigate('/hospitals');
      return;
    }

    setLoading(true);
    api.get(`/hospitals/${hospitalId}`)
      .then(res => {
        setHospital(res.data);
        // NEW: seed the textareas once the hospital data actually arrives
        setWelcomeMessage(res.data.welcome_message || '');
        setPostBookingDisclaimer(res.data.post_booking_disclaimer || '');
        setLoading(false);
      })
      .catch((err) => {
        console.error("Dashboard Fetch Error:", err);
        setHospital(null);
        setLoading(false);
      });
  }, [hospitalId, navigate]);

  // NEW: handler defined inside the component, before return, so JSX below can reference it
  const handleSaveHospitalConfig = async () => {
    setSavingConfig(true);
    try {
      await api.patch(`/hospitals/${hospitalId}`, {
        welcome_message: welcomeMessage,
        post_booking_disclaimer: postBookingDisclaimer,
      });
    } catch (err) {
      console.error("Failed to save hospital config:", err);
    } finally {
      setSavingConfig(false);
    }
  };

  if (loading) return <div className="p-8 text-center animate-pulse">Loading Command Center...</div>;

  if (!hospital) {
    return (
      <div className="p-8 text-center">
        <h1 className="text-2xl font-bold text-red-600">Hospital Not Found</h1>
        <p className="mt-2 text-gray-500">The hospital ID "{hospitalId}" does not exist in the cloud database.</p>
        <button 
          onClick={() => navigate('/hospitals')}
          className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          Back to Hospital List
        </button>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* HEADER SECTION */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b pb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Arogya Command Center</h1>
          <p className="text-gray-600">
            Managing: <span className="font-semibold text-blue-600">{hospital.name}</span>
          </p>
          <p className="text-xs text-gray-400 mt-1 uppercase tracking-wider">ID: {hospital.id} | SLUG: {hospital.slug}</p>
        </div>
        <button 
          onClick={() => navigate('/hospitals')}
          className="text-sm font-medium text-gray-500 hover:text-blue-600 transition-colors"
        >
          &larr; Switch Hospital
        </button>
      </div>

      {/* BILLING & ANALYTICS SECTION */}
      <section>
        <h2 className="text-xl font-semibold text-gray-800 mb-4">Business Analytics</h2>
        <HospitalStats hospitalId={Number(hospitalId)} />
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* TRAINING SECTION */}
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold">1</div>
            <h2 className="text-xl font-semibold text-gray-700">Train Your AI</h2>
          </div>

          <KnowledgeBaseUpload hospitalId={hospitalId} />

          {/* NEW: Welcome message + disclaimer live inside the SAME training column */}
          <div className="mb-6">
            <label className="block font-medium mb-1">Welcome Message</label>
            <p className="text-sm text-gray-500 mb-2">Shown to patients when they start a new chat session.</p>
            <textarea
              value={welcomeMessage}
              onChange={(e) => setWelcomeMessage(e.target.value)}
              placeholder="e.g. Welcome to Iris Rheumatology Clinic. Our process is..."
              className="w-full border rounded p-2"
              rows={3}
            />
          </div>

          <div className="mb-6">
            <label className="block font-medium mb-1">Post-Booking Disclaimer</label>
            <p className="text-sm text-gray-500 mb-2">Appended to the confirmation message after a booking is made.</p>
            <textarea
              value={postBookingDisclaimer}
              onChange={(e) => setPostBookingDisclaimer(e.target.value)}
              placeholder="e.g. Please note: waiting times may vary."
              className="w-full border rounded p-2"
              rows={2}
            />
          </div>

          <button
            onClick={handleSaveHospitalConfig}
            disabled={savingConfig}
            className="btn-primary"
          >
            {savingConfig ? 'Saving...' : 'Save'}
          </button>
        </div>

        {/* PREVIEW SECTION */}
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-green-100 text-green-600 flex items-center justify-center font-bold">2</div>
            <h2 className="text-xl font-semibold text-gray-700">Test Arogya Chat</h2>
          </div>
          <ChatPreview hospitalId={hospitalId} />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
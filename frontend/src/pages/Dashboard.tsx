import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom'; 
import api from '../api/axios';
import KnowledgeBaseUpload from './KnowledgeBase'; 
import ChatPreview from '../components/ChatPreview'; 
import HospitalStats from '../components/HospitalStats'; 
import { MessageSquare, AlertTriangle, Shield } from 'lucide-react';

const Dashboard = () => {
  const { hospitalId } = useParams(); 
  const navigate = useNavigate();
  const [hospital, setHospital] = useState(null);
  const [loading, setLoading] = useState(true);

  // NEW: state for welcome message + disclaimer — declared with the other hooks, at top level
  const [welcomeMessage, setWelcomeMessage] = useState('');
  const [postBookingDisclaimer, setPostBookingDisclaimer] = useState('');
  const [relevanceCriteria, setRelevanceCriteria] = useState('');
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
        setRelevanceCriteria(res.data.relevance_criteria || '');
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
        relevance_criteria: relevanceCriteria,
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
          <div className="space-y-6">
            <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-5 shadow-sm">
              <div className="flex items-center gap-2 mb-2 text-indigo-700">
                <MessageSquare className="w-5 h-5" />
                <label className="font-semibold text-lg">Welcome Message</label>
              </div>
              <p className="text-sm text-indigo-600/80 mb-3">Shown to patients when they start a new chat session.</p>
              <textarea
                value={welcomeMessage}
                onChange={(e) => setWelcomeMessage(e.target.value)}
                placeholder="e.g. Welcome to Iris Rheumatology Clinic. Our process is..."
                className="w-full border-0 bg-white ring-1 ring-indigo-200 focus:ring-2 focus:ring-indigo-400 rounded-lg p-3 text-sm text-slate-700"
                rows={3}
              />
            </div>

            <div className="bg-amber-50 border border-amber-100 rounded-xl p-5 shadow-sm">
              <div className="flex items-center gap-2 mb-2 text-amber-700">
                <AlertTriangle className="w-5 h-5" />
                <label className="font-semibold text-lg">Post-Booking Disclaimer</label>
              </div>
              <p className="text-sm text-amber-700/80 mb-3">Appended to the confirmation message after a booking is made.</p>
              <textarea
                value={postBookingDisclaimer}
                onChange={(e) => setPostBookingDisclaimer(e.target.value)}
                placeholder="e.g. Please note: waiting times may vary."
                className="w-full border-0 bg-white ring-1 ring-amber-200 focus:ring-2 focus:ring-amber-400 rounded-lg p-3 text-sm text-slate-700"
                rows={2}
              />
            </div>

            <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-5 shadow-sm">
              <div className="flex items-center gap-2 mb-2 text-emerald-700">
                <Shield className="w-5 h-5" />
                <label className="font-semibold text-lg">Relevance Gate Criteria</label>
              </div>
              <p className="text-sm text-emerald-700/80 mb-3">Leave blank to disable the relevance gate for this hospital. If set, AI will ask follow-up questions to check if the patient matches these rules.</p>
              <textarea
                value={relevanceCriteria}
                onChange={(e) => setRelevanceCriteria(e.target.value)}
                placeholder="e.g. Must be over 18. Must have joint pain for more than 2 weeks."
                className="w-full border-0 bg-white ring-1 ring-emerald-200 focus:ring-2 focus:ring-emerald-400 rounded-lg p-3 text-sm text-slate-700"
                rows={3}
              />
            </div>
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
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom'; 
import api from '../api/axios';
import KnowledgeBaseUpload from './KnowledgeBase'; 
import ChatPreview from '../components/ChatPreview'; 

const Dashboard = () => {
  const { hospitalId } = useParams(); 
  const navigate = useNavigate();
  const [hospital, setHospital] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // If there is no ID in the URL, redirect them to the hospital list
    if (!hospitalId) {
      navigate('/hospitals'); // Or wherever your list page is
      return;
    }

    setLoading(true);
    api.get(`/hospitals/${hospitalId}`)
      .then(res => {
        setHospital(res.data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Dashboard Fetch Error:", err);
        setHospital(null);
        setLoading(false);
      });
  }, [hospitalId, navigate]);

  if (loading) return <div className="p-8">Loading Command Center...</div>;

  if (!hospital) {
    return (
      <div className="p-8 text-center">
        <h1 className="text-2xl font-bold text-red-600">Hospital Not Found</h1>
        <p className="mt-2">The hospital ID "{hospitalId}" does not exist in the cloud database.</p>
        <button 
          onClick={() => navigate('/hospitals')}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg"
        >
          Back to Hospital List
        </button>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-800">Arogya Command Center</h1>
        <p className="mt-2 text-gray-600">
          Active Hospital: <span className="font-semibold text-blue-600">{hospital.name}</span>
        </p>
        <p className="text-xs text-gray-400">Database ID: {hospital.id} | Slug: {hospital.slug}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-gray-700">1. Train Your AI</h2>
          <KnowledgeBaseUpload hospitalId={hospitalId} />
        </div>

        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-gray-700">2. Test Arogya Chat</h2>
          <ChatPreview hospitalId={hospitalId} />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
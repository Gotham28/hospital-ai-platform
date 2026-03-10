import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom'; // Import this
import api from '../api/axios';
import KnowledgeBaseUpload from './KnowledgeBase'; 
import ChatPreview from '../components/ChatPreview'; 

const Dashboard = () => {
  const { hospitalId } = useParams(); // Extract ID from the URL
  const [hospitalName, setHospitalName] = useState('Loading...');

  useEffect(() => {
    // Fetch specific hospital data using the ID from the URL
    api.get(`/hospitals/${hospitalId}`)
      .then(res => setHospitalName(res.data.name))
      .catch(() => setHospitalName('Hospital Not Found'));
  }, [hospitalId]);

  return (
    <div className="p-8 space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-800">Arogya Command Center</h1>
        <p className="mt-2 text-gray-600">
          Active Hospital: <span className="font-semibold text-blue-600">{hospitalName}</span>
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Phase 1: Knowledge Ingestion */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-gray-700">1. Train Your AI</h2>
          {/* We pass the hospitalId so the upload goes to the right place */}
          <KnowledgeBaseUpload hospitalId={hospitalId} />
        </div>

        {/* Phase 2: RAG Chat Preview */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-gray-700">2. Test Arogya Chat</h2>
          {/* We pass the hospitalId so the chat talks to the right brain */}
          <ChatPreview hospitalId={hospitalId} />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
import React from 'react';
import './bkm-hospital.css'; 

// Make sure you have copied Chat.tsx from the arogya folder into this folder!
import Chat from './Chat'; 

interface ThemeProps {
  hospitalId?: number;
  hospitalName?: string;
}

const BkmHospitalTheme: React.FC<ThemeProps> = ({ hospitalId, hospitalName }) => {
  return (
    <div className="bkm-theme-wrapper flex flex-col h-screen">
      
      {/* 1. Custom Header */}
      <header className="bkm-header">
        <div className="bkm-logo-text">
          {hospitalName || 'BKM Hospital'} <span className="bkm-logo-accent">Payannur</span>
        </div>
      </header>

      {/* 2. Main Content Area */}
      <main className="flex-1 p-6 flex justify-center items-center">
        
        {/* 3. The Chatbot Container */}
        <div className="bkm-chat-container w-full max-w-4xl h-[80vh] flex flex-col">
          {hospitalId ? (
             <Chat hospitalId={hospitalId} />
          ) : (
            <div className="p-10 text-center text-white">
              <h2>Error: No Hospital ID received from backend.</h2>
            </div>
          )}
        </div>

      </main>
    </div>
  );
};

export default BkmHospitalTheme;
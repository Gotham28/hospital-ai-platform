import React from 'react';
import './bkm-hospital.css'; // <-- Import the new theme
import Chat from './Chat';

const BkmHospitalTheme: React.FC<{hospitalId?: number, hospitalName?: string}> = ({ hospitalId, hospitalName }) => {
  return (
    <div className="bkm-theme-wrapper">
       {/* Your custom TSX using the classes defined above */}
    </div>
  );
}
export default BkmHospitalTheme;
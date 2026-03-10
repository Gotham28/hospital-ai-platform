import React, { Suspense, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getThemeComponent } from './registry'; // Use the dynamic function
import api from '../api/axios';

const ThemeLoader = () => {
  const { hospitalSlug } = useParams<{ hospitalSlug: string }>();
  const [hospitalData, setHospitalData] = useState<{ id: number; name: string } | null>(null);

  // Dynamically find the component based on the URL slug
  const SelectedTheme = hospitalSlug ? getThemeComponent(hospitalSlug) : null;

  useEffect(() => {
  if (hospitalSlug) {
    // REMOVE '/api/v1' from the string! 
    // Axios adds it automatically from your config.
    api.get(`/hospitals/slug/${hospitalSlug}`) 
      .then(res => {
        setHospitalData(res.data);
      })
      .catch(err => {
        console.error("Backend Lookup Failed for Slug:", hospitalSlug, err);
      });
  }
}, [hospitalSlug]);

  if (!SelectedTheme) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-800">404</h1>
          <p className="text-gray-500">This hospital portal has not been designed yet.</p>
        </div>
      </div>
    );
  }

  return (
    <Suspense fallback={<div className="h-screen flex items-center justify-center">Loading Portal...</div>}>
      {hospitalData ? (
        <SelectedTheme hospitalId={hospitalData.id} hospitalName={hospitalData.name} />
      ) : (
        <div className="h-screen flex items-center justify-center">Connecting to Arogya Brain...</div>
      )}
    </Suspense>
  );
};

export default ThemeLoader;
import React from 'react';

// Finds all index.tsx files in subfolders
const themeModules = import.meta.glob('./**/index.tsx');

export const getThemeComponent = (slug: string) => {
  const normalizedSlug = slug.toLowerCase().trim();
  
  // Dynamically find the path that contains the slug as a folder name
  // This works whether the key is './bkm-hospital-payannur/index.tsx' 
  // or './themes/bkm-hospital-payannur/index.tsx'
  const matchedKey = Object.keys(themeModules).find((key) => 
    key.endsWith(`/${normalizedSlug}/index.tsx`) || key === `./${normalizedSlug}/index.tsx`
  );
  
  if (matchedKey && themeModules[matchedKey]) {
    return React.lazy(themeModules[matchedKey] as any);
  }

  // Debugging help: logs all found paths if one fails
  console.warn(`Theme not found for slug: ${normalizedSlug}. Available:`, Object.keys(themeModules));
  return null;
};
import React from 'react';

// Finds all index.tsx files in any subfolder of 'themes'
const themeModules = import.meta.glob('./**/index.tsx');

export const getThemeComponent = (slug: string) => {
  // We want to find a key that looks like './arogya/index.tsx'
  const normalizedSlug = slug.toLowerCase().trim();
  const pathKey = `./${normalizedSlug}/index.tsx`;
  
  if (themeModules[pathKey]) {
    return React.lazy(themeModules[pathKey] as any);
  }

  // Debugging help: logs all found paths if one fails
  console.warn(`Theme not found for: ${pathKey}. Available:`, Object.keys(themeModules));
  return null;
};
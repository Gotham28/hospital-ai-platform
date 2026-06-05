/**
 * IrisPage.tsx
 * ─────────────────────────────────────────────────────────────────
 * NOTE: With the new themes/iris-hospitals/ folder in place, the
 * canonical IRIS URL is now:  /p/iris-hospitals
 * (served by ThemeLoader, exactly like arogya and bkm)
 *
 * This page is kept as a redirect so any existing bookmarks to
 * /iris continue to work.
 * ─────────────────────────────────────────────────────────────────
 */

import { Navigate } from 'react-router-dom';

export default function IrisPage() {
  // Redirect legacy /iris URL → canonical theme URL
  return <Navigate to="/p/iris-hospitals" replace />;
}

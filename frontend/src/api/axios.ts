import axios from 'axios';

/**
 * Hospital AI Platform - Axios Configuration
 * * This instance handles the 'Magic Key' (JWT) injection automatically.
 * It ensures every request to the backend includes the hospital_id 
 * encoded in the bearer token.
 */
const baseURL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000/api/v1'
  : 'https://hospital-ai-platform.onrender.com/api/v1';

const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add this temporary log to see what the browser is actually using
console.log("Current API BaseURL:", import.meta.env.VITE_API_URL);
// Request Interceptor: Attaches the JWT to every outgoing call
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    
    if (token) {
      // Every request now carries the 'Magic Key' verification
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response Interceptor: Handles global errors (like expired tokens)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // If the Magic Key is invalid or expired, boot to login
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
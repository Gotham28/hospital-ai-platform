import axios from 'axios';

/**
 * Hospital AI Platform - Axios Configuration
 * * This instance handles the 'Magic Key' (JWT) injection automatically.
 * It ensures every request to the backend includes the hospital_id 
 * encoded in the bearer token.
 */
const api = axios.create({
  // VITE_API_URL should be "http://localhost:8000/api/v1" in your .env
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

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
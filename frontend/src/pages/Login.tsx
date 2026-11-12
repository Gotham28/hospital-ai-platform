import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';
import GothosByline from '../components/common/GothosByline';

const inputClass =
  'w-full min-h-10 px-3 py-[9px] bg-white border border-gothos-muted rounded-gothos-field mt-1 text-[15px] text-gothos-ink outline-none focus:outline-[3px] focus:outline-solid focus:outline-gothos-focus focus:outline-offset-3';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('username', email);
      formData.append('password', password);

      const response = await api.post('/auth/login', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const token = response.data.access_token;
      const payload = JSON.parse(atob(token.split('.')[1]));
      login(token);

      // Staff go directly to their hospital's appointments page
      if (payload.role === 'staff') {
        navigate(`/hospitals/${payload.hospital_id}/appointments`);
      } else {
        navigate('/');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gothos-bg font-gothos text-gothos-ink">
      <form
        onSubmit={handleLogin}
        className="px-[30px] py-[26px] bg-white/64 border border-white/90 shadow-gothos-card rounded-gothos-card w-96"
      >
        <div className="flex flex-col items-center gap-1 mb-4">
          <span className="text-3xl font-bold tracking-[-0.03em] text-gothos-forest">AROGYA</span>
          <GothosByline />
        </div>
        <h2 className="text-2xl font-semibold mb-6 text-center text-gothos-ink">
          Hospital Admin Portal
        </h2>

        {error && (
          <p className="text-red-500 text-sm mb-4 p-3 bg-red-50 rounded-gothos-field border border-red-100">
            {error}
          </p>
        )}

        <div className="mb-4">
          <label className="block text-[11px] font-medium text-gothos-ink">Email</label>
          <input
            type="email"
            className={inputClass}
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            disabled={loading}
            autoComplete="email"
          />
        </div>

        <div className="mb-6">
          <label className="block text-[11px] font-medium text-gothos-ink">Password</label>
          <input
            type="password"
            className={inputClass}
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            disabled={loading}
            autoComplete="current-password"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-gothos-forest text-white text-[13px] font-semibold px-[22px] py-3 rounded-full transition-[transform,background-color] duration-[250ms] hover:bg-gothos-deep hover:-translate-y-0.5 motion-reduce:transition-none motion-reduce:hover:translate-y-0 disabled:opacity-[.68] disabled:cursor-not-allowed disabled:hover:translate-y-0 focus-visible:outline-[3px] focus-visible:outline-solid focus-visible:outline-gothos-focus focus-visible:outline-offset-3"
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
};

export default Login;
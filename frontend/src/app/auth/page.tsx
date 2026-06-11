'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useRouter } from 'next/navigation';
import { LayoutDashboard, ShieldCheck, Mail, Lock, User as UserIcon, Wallet } from 'lucide-react';

export default function AuthPage() {
  const { user, login, register } = useAuth();
  const router = useRouter();
  
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [currency, setCurrency] = useState('USD');
  
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) {
      router.push('/');
    }
  }, [user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    
    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await register({
          email,
          password,
          full_name: fullName,
          base_currency: currency,
        });
      }
      router.push('/');
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-brand-bg px-4 overflow-hidden">
      {/* Background glowing blobs */}
      <div className="glow-bg glow-cyan top-[-10%] left-[-10%]" />
      <div className="glow-bg glow-violet bottom-[-10%] right-[-10%]" />

      <div className="w-full max-w-md z-10">
        {/* Title / Brand Header */}
        <div className="flex flex-col items-center mb-8">
          <div className="flex items-center space-x-3 mb-2">
            <LayoutDashboard className="h-10 w-10 text-brand-cyan animate-pulse" />
            <span className="text-3xl font-bold tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-brand-cyan to-brand-violet">
              PortfolioIQ
            </span>
          </div>
          <p className="text-slate-400 text-sm text-center">
            Institutional-Grade Portfolio Risk Analyzer & Optimizer
          </p>
        </div>

        {/* Auth Card */}
        <div className="glass-card rounded-2xl p-8 shadow-2xl border border-brand-border">
          <h2 className="text-xl font-semibold text-slate-100 mb-6 text-center">
            {isLogin ? 'Sign In to Your Account' : 'Create New Account'}
          </h2>

          {error && (
            <div className="mb-4 p-3 bg-brand-red/10 border border-brand-red/35 rounded-lg text-brand-red text-sm text-center">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <div>
                <label className="block text-slate-400 text-xs font-semibold mb-1.5 uppercase tracking-wider">
                  Full Name
                </label>
                <div className="relative">
                  <UserIcon className="absolute left-3.5 top-3 h-5 w-5 text-slate-500" />
                  <input
                    type="text"
                    required
                    placeholder="John Doe"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full bg-brand-bg/60 border border-brand-border focus:border-brand-cyan focus:outline-none rounded-lg py-2.5 pl-11 pr-4 text-slate-100 placeholder-slate-600 transition-colors"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-slate-400 text-xs font-semibold mb-1.5 uppercase tracking-wider">
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-3 h-5 w-5 text-slate-500" />
                <input
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-brand-bg/60 border border-brand-border focus:border-brand-cyan focus:outline-none rounded-lg py-2.5 pl-11 pr-4 text-slate-100 placeholder-slate-600 transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-400 text-xs font-semibold mb-1.5 uppercase tracking-wider">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-3 h-5 w-5 text-slate-500" />
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-brand-bg/60 border border-brand-border focus:border-brand-cyan focus:outline-none rounded-lg py-2.5 pl-11 pr-4 text-slate-100 placeholder-slate-600 transition-colors"
                />
              </div>
            </div>

            {!isLogin && (
              <div>
                <label className="block text-slate-400 text-xs font-semibold mb-1.5 uppercase tracking-wider">
                  Base Currency
                </label>
                <div className="relative">
                  <Wallet className="absolute left-3.5 top-3 h-5 w-5 text-slate-500" />
                  <select
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    className="w-full bg-brand-bg/80 border border-brand-border focus:border-brand-cyan focus:outline-none rounded-lg py-2.5 pl-11 pr-4 text-slate-100 appearance-none transition-colors cursor-pointer"
                  >
                    <option value="USD">USD ($)</option>
                    <option value="INR">INR (₹)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="GBP">GBP (£)</option>
                  </select>
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full mt-4 bg-gradient-to-r from-brand-cyan to-brand-violet hover:opacity-90 active:scale-[0.98] transition-all text-slate-100 font-semibold py-2.5 rounded-lg flex items-center justify-center space-x-2 cursor-pointer shadow-lg shadow-brand-cyan/15"
            >
              {submitting ? (
                <div className="h-5 w-5 border-2 border-slate-100 border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <ShieldCheck className="h-5 w-5" />
                  <span>{isLogin ? 'Sign In' : 'Get Started'}</span>
                </>
              )}
            </button>
          </form>

          {/* Toggle Tab link */}
          <div className="mt-6 text-center text-sm">
            <span className="text-slate-400">
              {isLogin ? "Don't have an account? " : "Already have an account? "}
            </span>
            <button
              onClick={() => {
                setIsLogin(!isLogin);
                setError(null);
              }}
              className="text-brand-cyan font-semibold hover:underline cursor-pointer"
            >
              {isLogin ? 'Create Account' : 'Sign In'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

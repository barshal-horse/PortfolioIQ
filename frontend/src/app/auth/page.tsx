'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useRouter } from 'next/navigation';
import { LayoutDashboard, ShieldCheck, Mail, Lock } from 'lucide-react';

declare global {
  interface Window {
    firebase?: any;
    __FIREBASE_CONFIG__?: Record<string, string>;
  }
}

export default function AuthPage() {
  const { user, login, register } = useAuth();
  const router = useRouter();

  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  // Firebase config is injected via NEXT_PUBLIC_FIREBASE_* env vars (optional).
  const firebaseConfig = {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  };
  const googleEnabled = Boolean(
    firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId && firebaseConfig.appId
  );

  useEffect(() => {
    if (user) {
      router.push('/');
    }
  }, [user, router]);

  const handleGoogleSignIn = async () => {
    if (!googleEnabled) return;
    setError(null);
    setGoogleLoading(true);
    try {
      // Lazy-load the Firebase SDK only when the feature is configured
      const [{ initializeApp, getApps }, { getAuth, GoogleAuthProvider, signInWithPopup }] =
        await Promise.all([import('firebase/app'), import('firebase/auth')]);

      const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
      const auth = getAuth(app);
      const provider = new GoogleAuthProvider();

      const result = await signInWithPopup(auth, provider);
      const idToken = await result.user.getIdToken();

      // Exchange the Firebase ID token for PortfolioIQ JWTs
      const resp = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/auth/google`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_token: idToken }),
        }
      );
      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Google sign-in failed on the server');
      }
      const payload = await resp.json();
      const { setTokens } = await import('@/lib/api');
      setTokens(payload.data.access_token, payload.data.refresh_token);
      window.location.href = '/';
    } catch (err: any) {
      if (err?.code === 'auth/popup-closed-by-user' || err?.code === 'auth/cancelled-popup-request') {
        // User dismissed the popup — not an error worth showing
      } else {
        setError(err?.message || 'Google sign-in failed');
      }
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      if (isLogin) {
        await login(email, password);
      } else {
        // Only the essentials — name and currency are derived server-side
        await register({ email, password });
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
            {isLogin ? 'Sign In to Your Account' : 'Create Your Account'}
          </h2>

          {error && (
            <div className="mb-4 p-3 bg-brand-red/10 border border-brand-red/35 rounded-lg text-brand-red text-sm text-center">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
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
                  minLength={8}
                  placeholder={isLogin ? '••••••••' : 'At least 8 characters'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-brand-bg/60 border border-brand-border focus:border-brand-cyan focus:outline-none rounded-lg py-2.5 pl-11 pr-4 text-slate-100 placeholder-slate-600 transition-colors"
                />
              </div>
            </div>

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
                  <span>{isLogin ? 'Sign In' : 'Create Account'}</span>
                </>
              )}
            </button>
          </form>

          {/* Divider + Google sign-in */}
          <div className="flex items-center my-5">
            <div className="flex-1 h-px bg-brand-border" />
            <span className="px-3 text-[10px] uppercase tracking-wider text-slate-600">or</span>
            <div className="flex-1 h-px bg-brand-border" />
          </div>

          <button
            onClick={handleGoogleSignIn}
            disabled={!googleEnabled || googleLoading}
            title={
              googleEnabled
                ? 'Continue with Google'
                : 'Google sign-in requires NEXT_PUBLIC_FIREBASE_* env vars and FIREBASE_PROJECT_ID on the backend'
            }
            className="w-full bg-brand-card border border-brand-border hover:border-brand-border-focus active:scale-[0.98] transition-all text-slate-200 font-semibold py-2.5 rounded-lg flex items-center justify-center space-x-2.5 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {googleLoading ? (
              <div className="h-5 w-5 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <svg className="h-4.5 w-4.5" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    fill="#4285F4"
                    d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75z"
                  />
                </svg>
                <span>{isLogin ? 'Sign in with Google' : 'Sign up with Google'}</span>
              </>
            )}
          </button>

          {/* Toggle Tab link */}
          <div className="mt-6 text-center text-sm">
            <span className="text-slate-400">
              {isLogin ? "Don't have an account? " : 'Already have an account? '}
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

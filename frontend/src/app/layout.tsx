import type { Metadata } from 'next';
import { AuthProvider } from '@/context/AuthContext';
import './globals.css';

export const metadata: Metadata = {
  title: 'PortfolioIQ — Institutional-Grade AI Portfolio Analyzer & Optimizer',
  description: 'Track portfolio valuations, analyze statistical risk metrics (Sharpe, Sortino, VaR), compare performance against benchmarks, and receive AI-driven rebalancing recommendations.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}

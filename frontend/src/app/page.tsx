'use client';

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import {
  LayoutDashboard,
  TrendingUp,
  Activity,
  HeartPulse,
  Plus,
  Upload,
  Trash2,
  LogOut,
  DollarSign,
  AlertCircle,
  CheckCircle2,
  BarChart3,
  PieChart,
  PlusCircle,
  FileSpreadsheet,
  RefreshCw,
  Info,
  ChevronRight,
  TrendingDown
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart as ReChartsBarChart,
  Bar,
  LineChart,
  Line,
  Legend,
  Cell,
  PieChart as RechartsPieChart,
  Pie
} from 'recharts';

export default function DashboardPage() {
  const { user, loading: authLoading, logout } = useAuth();
  const router = useRouter();

  // Tab State
  const [activeTab, setActiveTab] = useState<'overview' | 'risk' | 'benchmark' | 'health'>('overview');

  // Portfolio State
  const [portfolios, setPortfolios] = useState<any[]>([]);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>('');
  const [portfolioDetails, setPortfolioDetails] = useState<any>(null);
  
  // Analytical States
  const [lookback, setLookback] = useState<number>(252);
  const [riskData, setRiskData] = useState<any>(null);
  const [riskContributions, setRiskContributions] = useState<any>(null);
  const [varDetails, setVarDetails] = useState<any>(null);
  const [benchmarkData, setBenchmarkData] = useState<any>(null);
  const [healthData, setHealthData] = useState<any>(null);
  
  // Loading states
  const [portfoliosLoading, setPortfoliosLoading] = useState(true);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [healthRefreshing, setHealthRefreshing] = useState(false);

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isAddHoldingModalOpen, setIsAddHoldingModalOpen] = useState(false);
  const [isUploadCsvOpen, setIsUploadCsvOpen] = useState(false);
  
  // Form fields
  const [newPortfolioName, setNewPortfolioName] = useState('');
  const [newPortfolioDesc, setNewPortfolioDesc] = useState('');
  const [newPortfolioBench, setNewPortfolioBench] = useState('SP500');
  
  const [newHoldingTicker, setNewHoldingTicker] = useState('');
  const [newHoldingQty, setNewHoldingQty] = useState('');
  const [newHoldingCost, setNewHoldingCost] = useState('');
  
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [csvUploadError, setCsvUploadError] = useState<string | null>(null);

  // Mounted helper for hydration
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Auth gate check
  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/auth');
    }
  }, [user, authLoading, router]);

  // Load portfolios
  useEffect(() => {
    if (user) {
      loadPortfolios();
    }
  }, [user]);

  // Fetch all dashboard analytics whenever selected portfolio or lookback changes
  useEffect(() => {
    if (selectedPortfolioId) {
      loadAllPortfolioAnalytics(selectedPortfolioId, lookback);
    } else {
      setPortfolioDetails(null);
      setRiskData(null);
      setRiskContributions(null);
      setVarDetails(null);
      setBenchmarkData(null);
      setHealthData(null);
    }
  }, [selectedPortfolioId, lookback]);

  const loadPortfolios = async () => {
    setPortfoliosLoading(true);
    try {
      const list = await api.portfolios.list();
      setPortfolios(list);
      if (list.length > 0 && !selectedPortfolioId) {
        setSelectedPortfolioId(list[0].id);
      }
    } catch (err) {
      console.error('Failed to load portfolios:', err);
    } finally {
      setPortfoliosLoading(false);
    }
  };

  const loadAllPortfolioAnalytics = async (id: string, days: number) => {
    setDetailsLoading(true);
    try {
      // Fetch core portfolio details
      const details = await api.portfolios.get(id);
      setPortfolioDetails(details);

      // If portfolio has holdings, load all calculations
      if (details.holdings && details.holdings.length > 0) {
        const [risk, contrib, varData, bench, health] = await Promise.all([
          api.risk.getRisk(id, days).catch(() => null),
          api.risk.getContributions(id).catch(() => null),
          api.risk.getVaR(id, 'historical', 0.95, 1).catch(() => null),
          api.benchmark.getComparison(id, days).catch(() => null),
          api.health.getHealth(id).catch(() => null),
        ]);
        setRiskData(risk);
        setRiskContributions(contrib);
        setVarDetails(varData);
        setBenchmarkData(bench);
        setHealthData(health);
      } else {
        setRiskData(null);
        setRiskContributions(null);
        setVarDetails(null);
        setBenchmarkData(null);
        setHealthData(null);
      }
    } catch (err) {
      console.error('Failed to load portfolio details:', err);
    } finally {
      setDetailsLoading(false);
    }
  };

  const handleCreatePortfolio = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const created = await api.portfolios.create({
        name: newPortfolioName,
        description: newPortfolioDesc,
        benchmark: newPortfolioBench,
        base_currency: 'USD'
      });
      setNewPortfolioName('');
      setNewPortfolioDesc('');
      setIsCreateModalOpen(false);
      await loadPortfolios();
      setSelectedPortfolioId(created.id);
    } catch (err) {
      alert('Error creating portfolio');
    }
  };

  const handleAddHolding = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.holdings.add(selectedPortfolioId, {
        ticker: newHoldingTicker.toUpperCase(),
        quantity: parseFloat(newHoldingQty),
        average_cost: parseFloat(newHoldingCost),
        currency: 'USD'
      });
      setNewHoldingTicker('');
      setNewHoldingQty('');
      setNewHoldingCost('');
      setIsAddHoldingModalOpen(false);
      loadAllPortfolioAnalytics(selectedPortfolioId, lookback);
    } catch (err) {
      alert('Error adding holding. Verify that ticker is correct.');
    }
  };

  const handleUploadCsv = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;
    setCsvUploadError(null);
    try {
      await api.portfolios.uploadCsv(selectedPortfolioId, selectedFile);
      setSelectedFile(null);
      setIsUploadCsvOpen(false);
      loadAllPortfolioAnalytics(selectedPortfolioId, lookback);
    } catch (err: any) {
      setCsvUploadError(err.message || 'Failed to parse or upload CSV.');
    }
  };

  const handleDeletePortfolio = async () => {
    if (!confirm('Are you sure you want to delete this portfolio and all its holdings?')) return;
    try {
      await api.portfolios.delete(selectedPortfolioId);
      const remaining = portfolios.filter(p => p.id !== selectedPortfolioId);
      setPortfolios(remaining);
      if (remaining.length > 0) {
        setSelectedPortfolioId(remaining[0].id);
      } else {
        setSelectedPortfolioId('');
      }
    } catch (err) {
      alert('Error deleting portfolio');
    }
  };

  const handleRefreshHealth = async () => {
    setHealthRefreshing(true);
    try {
      await api.health.refresh(selectedPortfolioId);
      const health = await api.health.getHealth(selectedPortfolioId);
      setHealthData(health);
    } catch (err) {
      console.error(err);
    } finally {
      setHealthRefreshing(false);
    }
  };

  // Sector allocation colors map
  const COLORS = ['#06B6D4', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#3B82F6', '#84CC16'];

  if (authLoading || portfoliosLoading) {
    return (
      <div className="min-h-screen bg-brand-bg flex items-center justify-center">
        <div className="flex flex-col items-center space-y-4">
          <div className="h-10 w-10 border-4 border-brand-cyan border-t-transparent rounded-full animate-spin" />
          <span className="text-slate-400 text-sm">Loading PortfolioIQ Dashboard...</span>
        </div>
      </div>
    );
  }

  // Formatting currency helper
  const formatCurrency = (val: number | null | undefined) => {
    if (val === undefined || val === null) return '$0.00';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: portfolioDetails?.base_currency || 'USD' }).format(val);
  };

  const formatPercent = (val: number | null | undefined) => {
    if (val === undefined || val === null) return '0.00%';
    return `${(val * 100).toFixed(2)}%`;
  };

  // Convert sector allocations to chart data format
  const sectorChartData = portfolioDetails?.sector_allocation
    ? Object.keys(portfolioDetails.sector_allocation).map((key) => ({
        name: key,
        value: portfolioDetails.sector_allocation[key]
      }))
    : [];

  // Valuation growth series
  const valuationChartData = riskData?.return_series?.dates?.map((d: string, idx: number) => {
    // Accumulate valuation indices for growth chart
    return {
      date: d,
      value: riskData?.drawdown_series?.dates // using return_series date alignment
        ? (riskData.return_series.values[idx] || 0.0)
        : 0.0
    };
  }) || [];

  return (
    <div className="flex min-h-screen bg-brand-bg text-slate-100">
      {/* BACKGROUND DECORATIVE GLOW */}
      <div className="glow-bg glow-cyan top-[10%] left-[5%]" />
      <div className="glow-bg glow-violet bottom-[15%] right-[5%]" />

      {/* SIDE NAVIGATION BAR */}
      <aside className="w-64 bg-brand-card/90 border-r border-brand-border flex flex-col z-10">
        <div className="h-20 flex items-center px-6 border-b border-brand-border">
          <LayoutDashboard className="h-8 w-8 text-brand-cyan mr-3 animate-pulse" />
          <span className="text-xl font-bold tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-brand-cyan to-brand-violet">
            PortfolioIQ
          </span>
        </div>
        
        {/* Navigation list */}
        <nav className="flex-1 px-4 py-6 space-y-1">
          <button
            onClick={() => setActiveTab('overview')}
            className={`w-full flex items-center px-4 py-3 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
              activeTab === 'overview'
                ? 'bg-brand-cyan/10 text-brand-cyan border-l-4 border-brand-cyan'
                : 'text-slate-400 hover:bg-brand-card/50 hover:text-slate-200'
            }`}
          >
            <PieChart className="h-5 w-5 mr-3" />
            Overview
          </button>
          
          <button
            onClick={() => setActiveTab('risk')}
            className={`w-full flex items-center px-4 py-3 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
              activeTab === 'risk'
                ? 'bg-brand-cyan/10 text-brand-cyan border-l-4 border-brand-cyan'
                : 'text-slate-400 hover:bg-brand-card/50 hover:text-slate-200'
            }`}
          >
            <Activity className="h-5 w-5 mr-3" />
            Risk Analytics
          </button>

          <button
            onClick={() => setActiveTab('benchmark')}
            className={`w-full flex items-center px-4 py-3 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
              activeTab === 'benchmark'
                ? 'bg-brand-cyan/10 text-brand-cyan border-l-4 border-brand-cyan'
                : 'text-slate-400 hover:bg-brand-card/50 hover:text-slate-200'
            }`}
          >
            <TrendingUp className="h-5 w-5 mr-3" />
            Benchmark Comparison
          </button>

          <button
            onClick={() => setActiveTab('health')}
            className={`w-full flex items-center px-4 py-3 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
              activeTab === 'health'
                ? 'bg-brand-cyan/10 text-brand-cyan border-l-4 border-brand-cyan'
                : 'text-slate-400 hover:bg-brand-card/50 hover:text-slate-200'
            }`}
          >
            <HeartPulse className="h-5 w-5 mr-3" />
            Health Score
          </button>
        </nav>

        {/* User Info / Log Out */}
        <div className="p-4 border-t border-brand-border">
          <div className="flex items-center justify-between mb-3 px-2">
            <div className="flex flex-col min-w-0">
              <span className="text-sm font-semibold text-slate-200 truncate">{user?.full_name}</span>
              <span className="text-xs text-slate-500 truncate">{user?.email}</span>
            </div>
            <button
              onClick={logout}
              className="text-slate-500 hover:text-brand-red p-1.5 rounded-lg hover:bg-brand-red/10 transition-colors cursor-pointer"
              title="Sign Out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* MAIN CONTAINER CONTENT */}
      <main className="flex-1 flex flex-col min-w-0 z-10 overflow-y-auto">
        {/* Top bar header */}
        <header className="h-20 bg-brand-card/30 border-b border-brand-border flex items-center justify-between px-8">
          <div className="flex items-center space-x-4">
            <span className="text-slate-400 text-sm font-semibold">Active Portfolio:</span>
            <div className="relative">
              {portfolios.length > 0 ? (
                <select
                  value={selectedPortfolioId}
                  onChange={(e) => setSelectedPortfolioId(e.target.value)}
                  className="bg-brand-card border border-brand-border rounded-xl px-4 py-2 text-slate-200 font-semibold cursor-pointer focus:outline-none focus:border-brand-cyan pr-8 appearance-none"
                >
                  {portfolios.map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              ) : (
                <span className="text-slate-500 text-sm">No portfolios. Create one first.</span>
              )}
              <div className="absolute right-3 top-3.5 h-4 w-4 border-b-2 border-r-2 border-slate-400 transform rotate-45 pointer-events-none scale-75" />
            </div>
            
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="bg-brand-cyan/15 hover:bg-brand-cyan/25 text-brand-cyan border border-brand-cyan/30 rounded-xl px-3 py-2 text-xs font-semibold flex items-center cursor-pointer transition-colors"
            >
              <Plus className="h-4 w-4 mr-1.5" />
              New Portfolio
            </button>
            
            {selectedPortfolioId && (
              <button
                onClick={handleDeletePortfolio}
                className="bg-brand-red/10 hover:bg-brand-red/20 text-brand-red border border-brand-red/20 rounded-xl px-3 py-2 text-xs font-semibold flex items-center cursor-pointer transition-colors"
              >
                <Trash2 className="h-4 w-4 mr-1.5" />
                Delete
              </button>
            )}
          </div>

          <div className="flex items-center space-x-3">
            {selectedPortfolioId && (
              <>
                <button
                  onClick={() => setIsAddHoldingModalOpen(true)}
                  className="bg-brand-cyan/80 hover:bg-brand-cyan hover:shadow-lg hover:shadow-brand-cyan/15 active:scale-[0.98] transition-all text-slate-100 rounded-xl px-4 py-2 text-sm font-semibold flex items-center cursor-pointer"
                >
                  <PlusCircle className="h-4.5 w-4.5 mr-1.5" />
                  Add Holding
                </button>
                
                <button
                  onClick={() => setIsUploadCsvOpen(true)}
                  className="bg-brand-violet/80 hover:bg-brand-violet hover:shadow-lg hover:shadow-brand-violet/15 active:scale-[0.98] transition-all text-slate-100 rounded-xl px-4 py-2 text-sm font-semibold flex items-center cursor-pointer"
                >
                  <FileSpreadsheet className="h-4.5 w-4.5 mr-1.5" />
                  Upload CSV
                </button>
              </>
            )}
          </div>
        </header>

        {/* DETAILS LOADING GRID */}
        {detailsLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex flex-col items-center space-y-3">
              <div className="h-8 w-8 border-4 border-brand-cyan border-t-transparent rounded-full animate-spin" />
              <span className="text-slate-400 text-sm">Calculating portfolio analytics...</span>
            </div>
          </div>
        ) : !selectedPortfolioId ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <LayoutDashboard className="h-16 w-16 text-slate-600 mb-4 animate-bounce" />
            <h3 className="text-xl font-bold text-slate-300 mb-2">Welcome to PortfolioIQ</h3>
            <p className="text-slate-500 max-w-sm mb-6">
              Create an investment portfolio and add holdings or upload a CSV file to evaluate your risk metrics and health score.
            </p>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="bg-gradient-to-r from-brand-cyan to-brand-violet text-slate-100 px-6 py-3 rounded-xl font-semibold hover:shadow-lg cursor-pointer"
            >
              Create First Portfolio
            </button>
          </div>
        ) : !portfolioDetails?.holdings || portfolioDetails.holdings.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <FileSpreadsheet className="h-16 w-16 text-slate-600 mb-4" />
            <h3 className="text-xl font-bold text-slate-300 mb-2">No Holdings Found</h3>
            <p className="text-slate-500 max-w-sm mb-6">
              Your portfolio &apos;{portfolioDetails?.name}&apos; is currently empty. Add assets or import a transaction file to view analytical tools.
            </p>
            <div className="flex space-x-4">
              <button
                onClick={() => setIsAddHoldingModalOpen(true)}
                className="bg-brand-cyan/80 hover:bg-brand-cyan text-slate-100 px-5 py-2.5 rounded-xl font-semibold cursor-pointer"
              >
                Add Manual Holdings
              </button>
              <button
                onClick={() => setIsUploadCsvOpen(true)}
                className="bg-brand-violet/80 hover:bg-brand-violet text-slate-100 px-5 py-2.5 rounded-xl font-semibold cursor-pointer"
              >
                Upload CSV
              </button>
            </div>
          </div>
        ) : (
          <div className="p-8 space-y-8 max-w-7xl mx-auto w-full">
            {/* LOOKBACK CONTROLLER */}
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-slate-100">{portfolioDetails.name}</h1>
                <p className="text-slate-400 text-sm mt-0.5">{portfolioDetails.description || 'No description provided.'}</p>
              </div>
              
              <div className="flex items-center space-x-2 bg-brand-card/50 p-1 border border-brand-border rounded-xl">
                {[
                  { label: '30D', val: 30 },
                  { label: '90D', val: 90 },
                  { label: '1Y (252D)', val: 252 },
                  { label: '3Y (756D)', val: 756 },
                ].map(item => (
                  <button
                    key={item.val}
                    onClick={() => setLookback(item.val)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                      lookback === item.val
                        ? 'bg-brand-cyan text-brand-bg shadow'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* TAB OVERVIEW PANEL */}
            {activeTab === 'overview' && (
              <div className="space-y-8">
                {/* Metrics Summary Card Row */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                  <div className="glass-card rounded-2xl p-6 border border-brand-border flex items-center justify-between">
                    <div>
                      <span className="text-slate-400 text-xs font-bold uppercase tracking-wider">Total Value</span>
                      <h3 className="text-2xl font-bold mt-1 text-slate-100">{formatCurrency(portfolioDetails.total_value)}</h3>
                    </div>
                    <div className="p-3 bg-brand-cyan/10 rounded-xl text-brand-cyan">
                      <DollarSign className="h-6 w-6" />
                    </div>
                  </div>
                  
                  <div className="glass-card rounded-2xl p-6 border border-brand-border flex items-center justify-between">
                    <div>
                      <span className="text-slate-400 text-xs font-bold uppercase tracking-wider">Cost Basis</span>
                      <h3 className="text-2xl font-bold mt-1 text-slate-100">{formatCurrency(portfolioDetails.total_cost)}</h3>
                    </div>
                    <div className="p-3 bg-slate-500/10 rounded-xl text-slate-400">
                      <DollarSign className="h-6 w-6" />
                    </div>
                  </div>
                  
                  <div className="glass-card rounded-2xl p-6 border border-brand-border flex items-center justify-between">
                    <div>
                      <span className="text-slate-400 text-xs font-bold uppercase tracking-wider">Unrealized PnL</span>
                      <h3 className={`text-2xl font-bold mt-1 ${portfolioDetails.unrealized_pnl >= 0 ? 'text-brand-green' : 'text-brand-red'}`}>
                        {formatCurrency(portfolioDetails.unrealized_pnl)}
                      </h3>
                    </div>
                    <div className={`p-3 rounded-xl ${portfolioDetails.unrealized_pnl >= 0 ? 'bg-brand-green/10 text-brand-green' : 'bg-brand-red/10 text-brand-red'}`}>
                      {portfolioDetails.unrealized_pnl >= 0 ? <TrendingUp className="h-6 w-6" /> : <TrendingDown className="h-6 w-6" />}
                    </div>
                  </div>

                  <div className="glass-card rounded-2xl p-6 border border-brand-border flex items-center justify-between">
                    <div>
                      <span className="text-slate-400 text-xs font-bold uppercase tracking-wider">Total Return %</span>
                      <h3 className={`text-2xl font-bold mt-1 ${portfolioDetails.pnl_percentage >= 0 ? 'text-brand-green' : 'text-brand-red'}`}>
                        {formatPercent(portfolioDetails.pnl_percentage)}
                      </h3>
                    </div>
                    <div className={`p-3 rounded-xl ${portfolioDetails.pnl_percentage >= 0 ? 'bg-brand-green/10 text-brand-green' : 'bg-brand-red/10 text-brand-red'}`}>
                      {portfolioDetails.pnl_percentage >= 0 ? <TrendingUp className="h-6 w-6" /> : <TrendingDown className="h-6 w-6" />}
                    </div>
                  </div>
                </div>

                {/* Charts Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Valuation Growth history */}
                  <div className="glass-card rounded-2xl p-6 border border-brand-border lg:col-span-2 flex flex-col">
                    <h3 className="text-lg font-bold text-slate-200 mb-6">Valuation Performance History</h3>
                    <div className="h-72 w-full flex-1">
                      {mounted && valuationChartData.length > 0 ? (
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={valuationChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <defs>
                              <linearGradient id="colorValuation" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#06B6D4" stopOpacity={0.25}/>
                                <stop offset="95%" stopColor="#06B6D4" stopOpacity={0}/>
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
                            <XAxis dataKey="date" stroke="#64748B" fontSize={10} tickLine={false} />
                            <YAxis stroke="#64748B" fontSize={10} tickLine={false} tickFormatter={(val) => `$${val.toLocaleString()}`} />
                            <Tooltip
                              contentStyle={{ backgroundColor: '#131B2E', borderColor: '#1E293B', borderRadius: 8 }}
                              labelStyle={{ fontWeight: 'bold', color: '#64748B' }}
                            />
                            <Area type="monotone" dataKey="value" stroke="#06B6D4" strokeWidth={2} fillOpacity={1} fill="url(#colorValuation)" name="Portfolio Value" />
                          </AreaChart>
                        </ResponsiveContainer>
                      ) : (
                        <div className="h-full flex items-center justify-center text-slate-500 text-sm">Generating performance chart...</div>
                      )}
                    </div>
                  </div>

                  {/* Sector Allocation Donut */}
                  <div className="glass-card rounded-2xl p-6 border border-brand-border flex flex-col">
                    <h3 className="text-lg font-bold text-slate-200 mb-6">Sector Allocation</h3>
                    <div className="h-56 w-full flex-1 relative flex items-center justify-center">
                      {mounted && sectorChartData.length > 0 ? (
                        <ResponsiveContainer width="100%" height="100%">
                          <RechartsPieChart>
                            <Pie
                              data={sectorChartData}
                              cx="50%"
                              cy="50%"
                              innerRadius={60}
                              outerRadius={80}
                              paddingAngle={4}
                              dataKey="value"
                            >
                              {sectorChartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                              ))}
                            </Pie>
                            <Tooltip
                              contentStyle={{ backgroundColor: '#131B2E', borderColor: '#1E293B', borderRadius: 8 }}
                              formatter={(value: any) => formatPercent(parseFloat(value))}
                            />
                          </RechartsPieChart>
                        </ResponsiveContainer>
                      ) : (
                        <div className="text-slate-500 text-sm">No sectors to allocate</div>
                      )}
                    </div>
                    {/* Legend */}
                    <div className="mt-4 grid grid-cols-2 gap-2 max-h-24 overflow-y-auto pr-2">
                      {sectorChartData.map((s, idx) => (
                        <div key={s.name} className="flex items-center space-x-2 text-xs">
                          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                          <span className="text-slate-400 truncate w-24">{s.name}</span>
                          <span className="text-slate-200 font-bold ml-auto">{formatPercent(s.value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Holdings list table */}
                <div className="glass-card rounded-2xl border border-brand-border overflow-hidden">
                  <div className="px-6 py-5 border-b border-brand-border">
                    <h3 className="text-lg font-bold text-slate-200">Asset Holdings Allocation</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-slate-300">
                      <thead className="bg-brand-card/45 text-slate-400 text-xs font-bold uppercase tracking-wider border-b border-brand-border">
                        <tr>
                          <th className="px-6 py-4">Ticker</th>
                          <th className="px-6 py-4">Sector</th>
                          <th className="px-6 py-4 text-right">Quantity</th>
                          <th className="px-6 py-4 text-right">Avg Cost</th>
                          <th className="px-6 py-4 text-right">Current Price</th>
                          <th className="px-6 py-4 text-right">Current Value</th>
                          <th className="px-6 py-4 text-right">Unrealized PnL</th>
                          <th className="px-6 py-4 text-right">Weight</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-brand-border">
                        {portfolioDetails.holdings.map((h: any) => (
                          <tr key={h.id} className="hover:bg-brand-card/25 transition-colors">
                            <td className="px-6 py-4 font-bold text-slate-100">{h.ticker}</td>
                            <td className="px-6 py-4 text-slate-400">{h.sector || 'N/A'}</td>
                            <td className="px-6 py-4 text-right font-mono">{h.quantity}</td>
                            <td className="px-6 py-4 text-right font-mono">{formatCurrency(h.average_cost)}</td>
                            <td className="px-6 py-4 text-right font-mono">{formatCurrency(h.current_price)}</td>
                            <td className="px-6 py-4 text-right font-bold text-slate-200 font-mono">{formatCurrency(h.current_value)}</td>
                            <td className={`px-6 py-4 text-right font-bold font-mono ${h.unrealized_pnl >= 0 ? 'text-brand-green' : 'text-brand-red'}`}>
                              {formatCurrency(h.unrealized_pnl)} ({formatPercent((h.current_price - h.average_cost)/h.average_cost)})
                            </td>
                            <td className="px-6 py-4 text-right font-mono">{formatPercent(h.weight)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* TAB RISK ANALYTICS PANEL */}
            {activeTab === 'risk' && (
              <div className="space-y-8">
                {/* Risk metrics ratios grid */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                  {[
                    { title: 'Annualized Volatility', val: riskData?.metrics?.annualized_volatility, desc: 'Portfolio volatility annualized', percent: true },
                    { title: 'Sharpe Ratio', val: riskData?.metrics?.sharpe_ratio, desc: 'Return per unit of total risk (rf=5%)' },
                    { title: 'Sortino Ratio', val: riskData?.metrics?.sortino_ratio, desc: 'Return per unit of downside deviation' },
                    { title: 'Jensen\'s Alpha', val: riskData?.metrics?.alpha, desc: 'Active return relative to beta exposure', percent: true },
                    { title: 'Beta vs Index', val: riskData?.metrics?.beta, desc: 'Market sensitivity relative to benchmark' },
                    { title: 'Tracking Error', val: riskData?.metrics?.tracking_error, desc: 'Standard deviation of excess returns', percent: true },
                    { title: 'Information Ratio', val: riskData?.metrics?.information_ratio, desc: 'Active returns consistency ratio' },
                    { title: 'Calmar Ratio', val: riskData?.metrics?.calmar_ratio, desc: 'Annualized return divided by Max Drawdown' },
                  ].map((metric) => (
                    <div key={metric.title} className="glass-card rounded-2xl p-6 border border-brand-border flex flex-col justify-between">
                      <div>
                        <span className="text-slate-400 text-xs font-bold uppercase tracking-wider">{metric.title}</span>
                        <h3 className="text-2xl font-bold mt-2 text-slate-100">
                          {metric.val !== undefined && metric.val !== null
                            ? metric.percent ? formatPercent(metric.val) : metric.val.toFixed(4)
                            : '0.00'}
                        </h3>
                      </div>
                      <p className="text-slate-500 text-xs mt-3 flex items-center">
                        <Info className="h-3.5 w-3.5 mr-1" />
                        {metric.desc}
                      </p>
                    </div>
                  ))}
                </div>

                {/* VaR & Contributions Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Tail risks VaR */}
                  <div className="glass-card rounded-2xl p-6 border border-brand-border flex flex-col">
                    <h3 className="text-lg font-bold text-slate-200 mb-4">Tail Risk & Value at Risk (VaR)</h3>
                    {varDetails ? (
                      <div className="space-y-6 flex-1 flex flex-col justify-between">
                        <div className="p-4 bg-brand-bg/50 border border-brand-border rounded-xl">
                          <p className="text-slate-300 text-sm italic">&ldquo;{varDetails.interpretation}&rdquo;</p>
                        </div>
                        <div className="space-y-4">
                          <div className="flex justify-between border-b border-brand-border/60 pb-2">
                            <span className="text-slate-400 text-sm">Confidence Level</span>
                            <span className="text-slate-200 font-semibold">{formatPercent(varDetails.confidence)}</span>
                          </div>
                          <div className="flex justify-between border-b border-brand-border/60 pb-2">
                            <span className="text-slate-400 text-sm">Value at Risk (VaR) %</span>
                            <span className="text-slate-200 font-mono font-semibold">{formatPercent(varDetails.var)}</span>
                          </div>
                          <div className="flex justify-between border-b border-brand-border/60 pb-2">
                            <span className="text-slate-400 text-sm">VaR Potential Loss Amount</span>
                            <span className="text-brand-red font-mono font-bold">{formatCurrency(Math.abs(varDetails.var_amount))}</span>
                          </div>
                          <div className="flex justify-between border-b border-brand-border/60 pb-2">
                            <span className="text-slate-400 text-sm">Conditional VaR (CVaR)</span>
                            <span className="text-slate-200 font-mono font-semibold">{formatPercent(varDetails.cvar)}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-400 text-sm">CVaR Potential Loss Amount</span>
                            <span className="text-brand-red font-mono font-bold">{formatCurrency(Math.abs(varDetails.cvar_amount))}</span>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="h-full flex items-center justify-center text-slate-500 text-sm">Calculating Value-at-Risk...</div>
                    )}
                  </div>

                  {/* Euler Risk contributions */}
                  <div className="glass-card rounded-2xl p-6 border border-brand-border lg:col-span-2 flex flex-col">
                    <h3 className="text-lg font-bold text-slate-200 mb-6">Holding Risk Contributions (Euler Decomposition)</h3>
                    <div className="h-72 w-full flex-1">
                      {mounted && riskContributions?.contributions ? (
                        <ResponsiveContainer width="100%" height="100%">
                          <ReChartsBarChart data={riskContributions.contributions} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
                            <XAxis dataKey="ticker" stroke="#64748B" fontSize={10} tickLine={false} />
                            <YAxis stroke="#64748B" fontSize={10} tickLine={false} tickFormatter={(val) => `${val}%`} />
                            <Tooltip
                              contentStyle={{ backgroundColor: '#131B2E', borderColor: '#1E293B', borderRadius: 8 }}
                              formatter={(value: any) => [`${parseFloat(value).toFixed(2)}%`, 'Percentage Contribution']}
                            />
                            <Bar dataKey="percentage_contribution" fill="#8B5CF6" radius={[4, 4, 0, 0]} name="Risk Contribution">
                              {riskContributions.contributions.map((entry: any, index: number) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                              ))}
                            </Bar>
                          </ReChartsBarChart>
                        </ResponsiveContainer>
                      ) : (
                        <div className="h-full flex items-center justify-center text-slate-500 text-sm">Calculating Euler risk decomposition...</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB BENCHMARK ENGINE */}
            {activeTab === 'benchmark' && (
              <div className="space-y-8">
                {/* Growth index comparison */}
                <div className="glass-card rounded-2xl p-6 border border-brand-border flex flex-col">
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-lg font-bold text-slate-200">Cumulative Performance vs Benchmark</h3>
                    <div className="text-xs font-semibold text-slate-400 bg-brand-bg/50 px-3 py-1.5 border border-brand-border rounded-lg">
                      Index Ticker: {benchmarkData?.benchmark === 'SP500' ? '^GSPC (S&P 500)' : benchmarkData?.benchmark || 'Index'}
                    </div>
                  </div>
                  <div className="h-80 w-full">
                    {mounted && benchmarkData?.cumulative_comparison?.dates ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={benchmarkData.cumulative_comparison.dates.map((d: string, idx: number) => ({
                          date: d,
                          portfolio: benchmarkData.cumulative_comparison.portfolio[idx],
                          benchmark: benchmarkData.cumulative_comparison.benchmark[idx],
                        }))} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
                          <XAxis dataKey="date" stroke="#64748B" fontSize={10} tickLine={false} />
                          <YAxis stroke="#64748B" fontSize={10} tickLine={false} domain={['dataMin - 0.05', 'dataMax + 0.05']} />
                          <Tooltip contentStyle={{ backgroundColor: '#131B2E', borderColor: '#1E293B', borderRadius: 8 }} />
                          <Legend verticalAlign="top" height={36} />
                          <Line type="monotone" dataKey="portfolio" stroke="#06B6D4" strokeWidth={2} dot={false} name="Portfolio Growth" />
                          <Line type="monotone" dataKey="benchmark" stroke="#8B5CF6" strokeWidth={2} dot={false} name="Benchmark Growth" strokeDasharray="5 5" />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="h-full flex items-center justify-center text-slate-500 text-sm">Generating growth index chart...</div>
                    )}
                  </div>
                </div>

                {/* Capture ratios and rolling stats */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Capture ratio indicators */}
                  <div className="glass-card rounded-2xl p-6 border border-brand-border flex flex-col justify-between">
                    <div>
                      <h3 className="text-lg font-bold text-slate-200 mb-6">Capture Ratios</h3>
                      <div className="space-y-6">
                        <div className="space-y-2">
                          <div className="flex justify-between text-sm">
                            <span className="text-slate-400">Upside Capture Ratio</span>
                            <span className="text-brand-green font-bold">{(benchmarkData?.metrics?.upside_capture * 100).toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                            <div className="bg-brand-green h-full" style={{ width: `${Math.min(100, (benchmarkData?.metrics?.upside_capture || 0) * 100)}%` }} />
                          </div>
                          <span className="text-[10px] text-slate-500 block">Captures {((benchmarkData?.metrics?.upside_capture || 0) * 100).toFixed(1)}% of benchmark gains during up periods.</span>
                        </div>
                        
                        <div className="space-y-2">
                          <div className="flex justify-between text-sm">
                            <span className="text-slate-400">Downside Capture Ratio</span>
                            <span className="text-brand-red font-bold">{(benchmarkData?.metrics?.downside_capture * 100).toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                            <div className="bg-brand-red h-full" style={{ width: `${Math.min(100, (benchmarkData?.metrics?.downside_capture || 0) * 100)}%` }} />
                          </div>
                          <span className="text-[10px] text-slate-500 block">Captures {((benchmarkData?.metrics?.downside_capture || 0) * 100).toFixed(1)}% of benchmark losses during down periods.</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Rolling beta */}
                  <div className="glass-card rounded-2xl p-6 border border-brand-border flex flex-col">
                    <h3 className="text-lg font-bold text-slate-200 mb-4">60-Day Rolling Beta</h3>
                    <div className="h-44 w-full flex-1">
                      {mounted && benchmarkData?.rolling_beta?.dates ? (
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={benchmarkData.rolling_beta.dates.map((d: string, idx: number) => ({
                            date: d,
                            value: benchmarkData.rolling_beta.values[idx],
                          }))} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
                            <XAxis dataKey="date" stroke="#64748B" fontSize={8} tickLine={false} />
                            <YAxis stroke="#64748B" fontSize={8} tickLine={false} />
                            <Tooltip contentStyle={{ backgroundColor: '#131B2E', borderColor: '#1E293B', borderRadius: 8 }} />
                            <Area type="monotone" dataKey="value" stroke="#8B5CF6" strokeWidth={1.5} fill="#8B5CF6" fillOpacity={0.08} name="Rolling Beta" />
                          </AreaChart>
                        </ResponsiveContainer>
                      ) : (
                        <div className="h-full flex items-center justify-center text-slate-500 text-sm">Calculating rolling beta series...</div>
                      )}
                    </div>
                  </div>

                  {/* Rolling Correlation */}
                  <div className="glass-card rounded-2xl p-6 border border-brand-border flex flex-col">
                    <h3 className="text-lg font-bold text-slate-200 mb-4">60-Day Rolling Correlation</h3>
                    <div className="h-44 w-full flex-1">
                      {mounted && benchmarkData?.rolling_correlation?.dates ? (
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={benchmarkData.rolling_correlation.dates.map((d: string, idx: number) => ({
                            date: d,
                            value: benchmarkData.rolling_correlation.values[idx],
                          }))} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
                            <XAxis dataKey="date" stroke="#64748B" fontSize={8} tickLine={false} />
                            <YAxis stroke="#64748B" fontSize={8} tickLine={false} />
                            <Tooltip contentStyle={{ backgroundColor: '#131B2E', borderColor: '#1E293B', borderRadius: 8 }} />
                            <Area type="monotone" dataKey="value" stroke="#06B6D4" strokeWidth={1.5} fill="#06B6D4" fillOpacity={0.08} name="Rolling Correlation" />
                          </AreaChart>
                        </ResponsiveContainer>
                      ) : (
                        <div className="h-full flex items-center justify-center text-slate-500 text-sm">Calculating rolling correlation series...</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB PORTFOLIO HEALTH SCORE */}
            {activeTab === 'health' && (
              <div className="space-y-8">
                {/* Score panel gauge */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Gauge score card */}
                  <div className="glass-card rounded-2xl p-8 border border-brand-border flex flex-col items-center justify-center text-center relative overflow-hidden">
                    <h3 className="text-lg font-bold text-slate-200 mb-6">Overall Health Score</h3>
                    {healthData ? (
                      <div className="space-y-4">
                        {/* Radial Gauge SVG */}
                        <div className="relative w-44 h-44 flex items-center justify-center">
                          <svg className="w-full h-full transform -rotate-90">
                            {/* Background track */}
                            <circle
                              cx="88" cy="88" r="76"
                              stroke="rgba(30, 41, 59, 0.5)" strokeWidth="12" fill="transparent"
                            />
                            {/* Glowing active path */}
                            <circle
                              cx="88" cy="88" r="76"
                              stroke={healthData.overall.score >= 80 ? '#10B981' : healthData.overall.score >= 50 ? '#F97316' : '#EF4444'}
                              strokeWidth="12" fill="transparent"
                              strokeDasharray={2 * Math.PI * 76}
                              strokeDashoffset={2 * Math.PI * 76 * (1.0 - healthData.overall.score / 100)}
                              strokeLinecap="round"
                              className="transition-all duration-1000 ease-out"
                            />
                          </svg>
                          <div className="absolute flex flex-col items-center">
                            <span className="text-4xl font-extrabold tracking-tight text-slate-100">{healthData.overall.score}</span>
                            <span className={`text-xs font-bold uppercase tracking-widest mt-1 ${
                              healthData.overall.grade === 'excellent' ? 'text-brand-green' :
                              healthData.overall.grade === 'good' ? 'text-brand-cyan' :
                              healthData.overall.grade === 'fair' ? 'text-brand-orange' : 'text-brand-red'
                            }`}>{healthData.overall.grade}</span>
                          </div>
                        </div>
                        <p className="text-slate-400 text-xs mt-4 max-w-xs leading-relaxed italic">{healthData.overall.explanation}</p>
                        
                        <button
                          onClick={handleRefreshHealth}
                          disabled={healthRefreshing}
                          className="mt-4 inline-flex items-center space-x-2 bg-brand-border hover:bg-brand-border-focus text-slate-300 font-semibold px-4 py-2 rounded-xl text-xs transition-colors cursor-pointer"
                        >
                          <RefreshCw className={`h-3.5 w-3.5 ${healthRefreshing ? 'animate-spin' : ''}`} />
                          <span>Recalculate Health</span>
                        </button>
                      </div>
                    ) : (
                      <div className="h-full flex items-center justify-center text-slate-500 text-sm">Calculating portfolio health score...</div>
                    )}
                  </div>

                  {/* Subscore breakdowns */}
                  <div className="glass-card rounded-2xl p-8 border border-brand-border lg:col-span-2 flex flex-col justify-between">
                    <h3 className="text-lg font-bold text-slate-200 mb-6">Subscore Category Breakdown</h3>
                    {healthData ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {[
                          { title: 'Diversification', val: healthData.subscores.diversification, weight: '25%' },
                          { title: 'Risk Control', val: healthData.subscores.risk, weight: '30%' },
                          { title: 'Performance', val: healthData.subscores.performance, weight: '25%' },
                          { title: 'Efficiency', val: healthData.subscores.efficiency, weight: '20%' },
                        ].map((sub) => (
                          <div key={sub.title} className="p-4 bg-brand-bg/40 border border-brand-border/60 rounded-xl space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-semibold text-slate-300">{sub.title}</span>
                              <span className={`text-xs font-bold uppercase px-2 py-0.5 rounded ${
                                sub.val.grade === 'excellent' ? 'bg-brand-green/10 text-brand-green' :
                                sub.val.grade === 'good' ? 'bg-brand-cyan/10 text-brand-cyan' :
                                sub.val.grade === 'fair' ? 'bg-brand-orange/10 text-brand-orange' : 'bg-brand-red/10 text-brand-red'
                              }`}>{sub.val.grade} ({sub.val.score})</span>
                            </div>
                            {/* Subscore Progress Bar */}
                            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                              <div className={`h-full ${
                                sub.val.score >= 80 ? 'bg-brand-green' :
                                sub.val.score >= 50 ? 'bg-brand-orange' : 'bg-brand-red'
                              }`} style={{ width: `${sub.val.score}%` }} />
                            </div>
                            <p className="text-[11px] text-slate-400 leading-normal">{sub.val.details?.explanation || 'Calculation verified.'}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="h-full flex items-center justify-center text-slate-500 text-sm">Evaluating subscores...</div>
                    )}
                  </div>
                </div>

                {/* Priority actionable recommendations */}
                <div className="glass-card rounded-2xl border border-brand-border overflow-hidden">
                  <div className="px-6 py-5 border-b border-brand-border">
                    <h3 className="text-lg font-bold text-slate-200">Actionable AI Recommendations</h3>
                  </div>
                  <div className="p-6 space-y-4">
                    {healthData?.recommendations && healthData.recommendations.length > 0 ? (
                      healthData.recommendations.map((rec: any, idx: number) => (
                        <div key={idx} className={`flex items-start p-4 rounded-xl border ${
                          rec.priority === 'high' ? 'bg-brand-red/10 border-brand-red/25' :
                          rec.priority === 'medium' ? 'bg-brand-orange/10 border-brand-orange/20' : 'bg-brand-green/10 border-brand-green/20'
                        }`}>
                          <div className={`p-2 rounded-lg mr-4 ${
                            rec.priority === 'high' ? 'bg-brand-red/20 text-brand-red' :
                            rec.priority === 'medium' ? 'bg-brand-orange/20 text-brand-orange' : 'bg-brand-green/20 text-brand-green'
                          }`}>
                            <AlertCircle className="h-5 w-5" />
                          </div>
                          <div>
                            <div className="flex items-center space-x-2">
                              <span className="text-sm font-bold text-slate-100">{rec.action}</span>
                              <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                                rec.priority === 'high' ? 'bg-brand-red/20 text-brand-red' :
                                rec.priority === 'medium' ? 'bg-brand-orange/20 text-brand-orange' : 'bg-brand-green/20 text-brand-green'
                              }`}>{rec.priority} priority</span>
                            </div>
                            <p className="text-slate-400 text-xs mt-1 leading-relaxed">{rec.rationale}</p>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="flex flex-col items-center justify-center py-6 text-center">
                        <CheckCircle2 className="h-10 w-10 text-brand-green mb-2" />
                        <h4 className="font-semibold text-slate-200">Portfolio Health Optimal</h4>
                        <p className="text-slate-500 text-xs mt-1">No actionable improvements required at this time.</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* ── MODAL CREATE PORTFOLIO ────────────────────────────────────────── */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-brand-bg/85 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass-card rounded-2xl p-8 border border-brand-border w-full max-w-md shadow-2xl relative">
            <h3 className="text-lg font-bold text-slate-100 mb-6">Create New Portfolio</h3>
            <form onSubmit={handleCreatePortfolio} className="space-y-4">
              <div>
                <label className="block text-slate-400 text-xs font-semibold uppercase mb-1.5">Portfolio Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Long-Term Growth"
                  value={newPortfolioName}
                  onChange={(e) => setNewPortfolioName(e.target.value)}
                  className="w-full bg-brand-bg/60 border border-brand-border rounded-lg py-2 px-3 focus:outline-none focus:border-brand-cyan text-slate-100 text-sm"
                />
              </div>
              
              <div>
                <label className="block text-slate-400 text-xs font-semibold uppercase mb-1.5">Description</label>
                <textarea
                  placeholder="Strategy or description..."
                  value={newPortfolioDesc}
                  onChange={(e) => setNewPortfolioDesc(e.target.value)}
                  className="w-full bg-brand-bg/60 border border-brand-border rounded-lg py-2 px-3 focus:outline-none focus:border-brand-cyan text-slate-100 text-sm h-20"
                />
              </div>

              <div>
                <label className="block text-slate-400 text-xs font-semibold uppercase mb-1.5">Target Benchmark</label>
                <select
                  value={newPortfolioBench}
                  onChange={(e) => setNewPortfolioBench(e.target.value)}
                  className="w-full bg-brand-bg/80 border border-brand-border rounded-lg py-2.5 px-3 focus:outline-none focus:border-brand-cyan text-slate-100 text-sm"
                >
                  <option value="SP500">S&P 500 (^GSPC)</option>
                  <option value="NASDAQ100">Nasdaq 100 (^NDX)</option>
                  <option value="NIFTY50">Nifty 50 (^NSEI)</option>
                </select>
              </div>

              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-4 py-2 border border-brand-border hover:bg-brand-card rounded-lg text-sm text-slate-400 hover:text-slate-200 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-brand-cyan hover:bg-brand-cyan/90 text-brand-bg font-semibold rounded-lg text-sm cursor-pointer"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── MODAL ADD HOLDING MANUALLY ─────────────────────────────────────── */}
      {isAddHoldingModalOpen && (
        <div className="fixed inset-0 bg-brand-bg/85 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass-card rounded-2xl p-8 border border-brand-border w-full max-w-md shadow-2xl relative">
            <h3 className="text-lg font-bold text-slate-100 mb-6">Add Asset Holding</h3>
            <form onSubmit={handleAddHolding} className="space-y-4">
              <div>
                <label className="block text-slate-400 text-xs font-semibold uppercase mb-1.5">Ticker symbol</label>
                <input
                  type="text"
                  required
                  placeholder="e.g., AAPL"
                  value={newHoldingTicker}
                  onChange={(e) => setNewHoldingTicker(e.target.value)}
                  className="w-full bg-brand-bg/60 border border-brand-border rounded-lg py-2 px-3 focus:outline-none focus:border-brand-cyan text-slate-100 text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-slate-400 text-xs font-semibold uppercase mb-1.5">Quantity</label>
                  <input
                    type="number"
                    required
                    step="any"
                    placeholder="0.00"
                    value={newHoldingQty}
                    onChange={(e) => setNewHoldingQty(e.target.value)}
                    className="w-full bg-brand-bg/60 border border-brand-border rounded-lg py-2 px-3 focus:outline-none focus:border-brand-cyan text-slate-100 text-sm font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 text-xs font-semibold uppercase mb-1.5">Average Cost</label>
                  <input
                    type="number"
                    required
                    step="any"
                    placeholder="0.00"
                    value={newHoldingCost}
                    onChange={(e) => setNewHoldingCost(e.target.value)}
                    className="w-full bg-brand-bg/60 border border-brand-border rounded-lg py-2 px-3 focus:outline-none focus:border-brand-cyan text-slate-100 text-sm font-mono"
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setIsAddHoldingModalOpen(false)}
                  className="px-4 py-2 border border-brand-border hover:bg-brand-card rounded-lg text-sm text-slate-400 hover:text-slate-200 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-brand-cyan hover:bg-brand-cyan/90 text-brand-bg font-semibold rounded-lg text-sm cursor-pointer"
                >
                  Add holding
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── MODAL UPLOAD CSV ─────────────────────────────────────────────── */}
      {isUploadCsvOpen && (
        <div className="fixed inset-0 bg-brand-bg/85 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass-card rounded-2xl p-8 border border-brand-border w-full max-w-md shadow-2xl relative">
            <h3 className="text-lg font-bold text-slate-100 mb-6">Upload CSV Transactions</h3>
            {csvUploadError && (
              <div className="mb-4 p-3 bg-brand-red/10 border border-brand-red/25 rounded-lg text-brand-red text-xs text-center">
                {csvUploadError}
              </div>
            )}
            <form onSubmit={handleUploadCsv} className="space-y-4">
              <div className="border-2 border-dashed border-brand-border rounded-xl p-6 flex flex-col items-center justify-center hover:border-brand-cyan/40 transition-colors bg-brand-bg/20">
                <Upload className="h-10 w-10 text-slate-500 mb-3" />
                <input
                  type="file"
                  required
                  accept=".csv"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-brand-cyan/15 file:text-brand-cyan file:cursor-pointer hover:file:bg-brand-cyan/25 cursor-pointer"
                />
                <span className="text-[10px] text-slate-600 mt-2 block">CSV must contain columns: ticker, quantity, average_cost</span>
              </div>

              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setIsUploadCsvOpen(false)}
                  className="px-4 py-2 border border-brand-border hover:bg-brand-card rounded-lg text-sm text-slate-400 hover:text-slate-200 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!selectedFile}
                  className="px-4 py-2 bg-brand-cyan hover:bg-brand-cyan/90 text-brand-bg font-semibold rounded-lg text-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Upload
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

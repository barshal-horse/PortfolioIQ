export interface OptimizationConstraints {
  min_weight?: number;
  max_weight?: number;
  sector_limits?: Record<string, number>;
  turnover_limit?: number;
}

export interface BlackLittermanView {
  type: 'absolute' | 'relative';
  ticker?: string;
  long_ticker?: string;
  short_ticker?: string;
  expected_return?: number;
  expected_outperformance?: number;
  confidence: number;
}

export interface TradeRecommendation {
  ticker: string;
  action: 'buy' | 'sell' | 'hold';
  current_weight: number;
  target_weight: number;
  delta: number;
  estimated_amount: number;
}

export interface ExpectedMetrics {
  expected_return: number;
  expected_volatility: number;
  expected_sharpe: number;
}

export interface FrontierPosition {
  return: number;
  volatility: number;
}

export interface EfficientFrontierData {
  returns: number[];
  volatilities: number[];
  sharpe_ratios: number[];
  current_position?: FrontierPosition;
  optimal_position?: FrontierPosition;
}

export interface OptimizationResponseData {
  id: string;
  method: string;
  calculation_date: string;
  current_allocation: Record<string, number>;
  optimal_allocation: Record<string, number>;
  expected_metrics: ExpectedMetrics;
  current_metrics?: ExpectedMetrics;
  trades: TradeRecommendation[];
  efficient_frontier?: EfficientFrontierData;
  views?: any[];
  posterior_returns?: Record<string, number>;
}

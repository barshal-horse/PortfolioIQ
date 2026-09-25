export interface StressTestScenarioInfo {
    id: string;
    name: string;
    start_date: string;
    end_date: string;
    sp500_return: number;
    description: string;
}

export interface HoldingImpact {
    ticker: string;
    return: number;
    weight: number;
    contribution: number;
}

export interface SectorImpact {
    sector: string;
    return: number;
    weight: number;
    contribution: number;
}

export interface ScenarioResult {
    scenario: string;
    description: string;
    scenario_start: string;
    scenario_end: string;
    portfolio_return: number;
    max_drawdown: number;
    benchmark_return: number | null;
    recovery_days: number | null;
    holding_impacts: HoldingImpact[];
    sector_impacts: SectorImpact[];
    summary: string;
}

export interface StressTestResponseData {
    portfolio_id: string;
    calculation_date: string;
    scenarios: ScenarioResult[];
}

export interface StressTestHistoryItem {
    id: string;
    scenario: string;
    calculation_date: string | null;
    portfolio_return: number | null;
    max_drawdown: number | null;
    recovery_days: number | null;
    benchmark_return: number | null;
    summary: string | null;
}
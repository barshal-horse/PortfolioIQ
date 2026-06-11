# PortfolioIQ — Database Schema

> PostgreSQL 16 · SQLAlchemy 2.0 (Async) · Alembic Migrations

---

## 1. Schema Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        CORE DOMAIN                                   │
│  ┌─────────┐    ┌────────────┐    ┌──────────┐    ┌─────────────┐  │
│  │  users   │───▶│ portfolios │───▶│ holdings │───▶│transactions │  │
│  └─────────┘    └────────────┘    └──────────┘    └─────────────┘  │
│                                        │                             │
│                                        ▼                             │
│                                 ┌─────────────┐                     │
│                                 │ instruments  │                     │
│                                 └──────┬──────┘                     │
│                                        │                             │
│                                        ▼                             │
│                               ┌───────────────┐                     │
│                               │ price_history  │                     │
│                               └───────────────┘                     │
├──────────────────────────────────────────────────────────────────────┤
│                       ANALYTICS DOMAIN                               │
│  ┌─────────────────┐  ┌──────────────────────┐  ┌────────────────┐ │
│  │  risk_metrics    │  │benchmark_comparisons │  │ health_scores  │ │
│  └─────────────────┘  └──────────────────────┘  └────────────────┘ │
│  ┌─────────────────┐  ┌──────────────────────┐                     │
│  │optimization_runs│  │ stress_test_results  │                     │
│  └─────────────────┘  └──────────────────────┘                     │
├──────────────────────────────────────────────────────────────────────┤
│                        AI / AGENT DOMAIN                             │
│  ┌─────────────────┐  ┌──────────────────────┐                     │
│  │copilot_sessions │  │  copilot_messages    │                     │
│  └─────────────────┘  └──────────────────────┘                     │
├──────────────────────────────────────────────────────────────────────┤
│                       NEWS / INTELLIGENCE                            │
│  ┌─────────────────┐  ┌──────────────────────┐                     │
│  │  news_articles  │  │  sentiment_scores    │                     │
│  └─────────────────┘  └──────────────────────┘                     │
├──────────────────────────────────────────────────────────────────────┤
│                        REPORTING                                     │
│  ┌─────────────────┐                                                │
│  │    reports       │                                                │
│  └─────────────────┘                                                │
├──────────────────────────────────────────────────────────────────────┤
│                        SYSTEM                                        │
│  ┌─────────────────┐                                                │
│  │  cache_entries   │                                                │
│  └─────────────────┘                                                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Enum Types

```sql
-- Portfolio status
CREATE TYPE portfolio_status AS ENUM (
    'active',
    'archived',
    'draft'
);

-- Transaction type
CREATE TYPE transaction_type AS ENUM (
    'buy',
    'sell',
    'dividend',
    'split',
    'transfer_in',
    'transfer_out'
);

-- Instrument type
CREATE TYPE instrument_type AS ENUM (
    'equity',
    'etf',
    'mutual_fund',
    'bond',
    'index',
    'crypto',
    'commodity',
    'cash'
);

-- Exchange identifiers
CREATE TYPE exchange_code AS ENUM (
    'NSE',       -- National Stock Exchange (India)
    'BSE',       -- Bombay Stock Exchange (India)
    'NYSE',      -- New York Stock Exchange
    'NASDAQ',    -- NASDAQ
    'AMEX',      -- American Stock Exchange
    'LSE',       -- London Stock Exchange
    'OTHER'
);

-- Currency codes
CREATE TYPE currency_code AS ENUM (
    'USD',
    'INR',
    'EUR',
    'GBP'
);

-- Benchmark identifiers
CREATE TYPE benchmark_type AS ENUM (
    'NIFTY50',     -- ^NSEI
    'SENSEX',      -- ^BSESN
    'SP500',       -- ^GSPC
    'NASDAQ100'    -- ^NDX
);

-- Optimization method
CREATE TYPE optimization_method AS ENUM (
    'mean_variance',
    'max_sharpe',
    'min_variance',
    'risk_parity',
    'black_litterman'
);

-- Stress scenario type
CREATE TYPE stress_scenario AS ENUM (
    'gfc_2008',
    'covid_2020',
    'high_inflation_2022',
    'rate_shock_2022'
);

-- Report type
CREATE TYPE report_type AS ENUM (
    'executive_summary',
    'full_portfolio',
    'monthly_review',
    'health_report'
);

-- Copilot message role
CREATE TYPE message_role AS ENUM (
    'user',
    'assistant',
    'system',
    'tool'
);

-- Health score grade
CREATE TYPE health_grade AS ENUM (
    'excellent',   -- 80-100
    'good',        -- 60-79
    'fair',        -- 40-59
    'poor',        -- 20-39
    'critical'     -- 0-19
);
```

---

## 3. Core Domain Tables

### 3.1 `users`

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    base_currency   currency_code NOT NULL DEFAULT 'USD',
    risk_free_rate  DECIMAL(6,4) DEFAULT 0.0500,  -- 5.00% default
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
```

### 3.2 `portfolios`

```sql
CREATE TABLE portfolios (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    base_currency   currency_code NOT NULL DEFAULT 'USD',
    status          portfolio_status NOT NULL DEFAULT 'active',
    benchmark       benchmark_type DEFAULT 'SP500',
    total_value     DECIMAL(18,4) DEFAULT 0.0000,
    total_cost      DECIMAL(18,4) DEFAULT 0.0000,
    unrealized_pnl  DECIMAL(18,4) DEFAULT 0.0000,
    pnl_percentage  DECIMAL(10,4) DEFAULT 0.0000,
    last_analyzed   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(user_id, name)
);

CREATE INDEX idx_portfolios_user_id ON portfolios(user_id);
CREATE INDEX idx_portfolios_status ON portfolios(status);
```

### 3.3 `instruments`

```sql
CREATE TABLE instruments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(20) NOT NULL,
    name            VARCHAR(500) NOT NULL,
    instrument_type instrument_type NOT NULL DEFAULT 'equity',
    exchange        exchange_code DEFAULT 'OTHER',
    sector          VARCHAR(255),
    industry        VARCHAR(255),
    market_cap      BIGINT,                         -- In base currency smallest unit
    currency        currency_code NOT NULL DEFAULT 'USD',
    country         VARCHAR(100),
    isin            VARCHAR(12),                    -- International Securities ID
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB DEFAULT '{}',             -- Extra data (PE, div yield, etc.)
    last_updated    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(ticker, exchange)
);

CREATE INDEX idx_instruments_ticker ON instruments(ticker);
CREATE INDEX idx_instruments_sector ON instruments(sector);
CREATE INDEX idx_instruments_type ON instruments(instrument_type);
```

### 3.4 `holdings`

```sql
CREATE TABLE holdings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id    UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    instrument_id   UUID NOT NULL REFERENCES instruments(id),
    ticker          VARCHAR(20) NOT NULL,            -- Denormalized for fast access
    quantity        DECIMAL(18,6) NOT NULL,           -- Supports fractional shares
    average_cost    DECIMAL(18,4) NOT NULL,           -- Per-unit cost basis
    current_price   DECIMAL(18,4) DEFAULT 0.0000,
    current_value   DECIMAL(18,4) DEFAULT 0.0000,
    cost_basis      DECIMAL(18,4) DEFAULT 0.0000,    -- quantity × average_cost
    unrealized_pnl  DECIMAL(18,4) DEFAULT 0.0000,
    weight          DECIMAL(8,6) DEFAULT 0.000000,   -- Portfolio weight (0.0 – 1.0)
    currency        currency_code NOT NULL DEFAULT 'USD',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(portfolio_id, ticker)
);

CREATE INDEX idx_holdings_portfolio_id ON holdings(portfolio_id);
CREATE INDEX idx_holdings_ticker ON holdings(ticker);
CREATE INDEX idx_holdings_instrument_id ON holdings(instrument_id);
```

### 3.5 `transactions`

```sql
CREATE TABLE transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id    UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    holding_id      UUID REFERENCES holdings(id) ON DELETE SET NULL,
    ticker          VARCHAR(20) NOT NULL,
    transaction_type transaction_type NOT NULL,
    quantity        DECIMAL(18,6) NOT NULL,
    price           DECIMAL(18,4) NOT NULL,
    total_amount    DECIMAL(18,4) NOT NULL,           -- quantity × price
    fees            DECIMAL(18,4) DEFAULT 0.0000,
    currency        currency_code NOT NULL DEFAULT 'USD',
    transaction_date DATE NOT NULL,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_transactions_portfolio_id ON transactions(portfolio_id);
CREATE INDEX idx_transactions_holding_id ON transactions(holding_id);
CREATE INDEX idx_transactions_ticker ON transactions(ticker);
CREATE INDEX idx_transactions_date ON transactions(transaction_date);
```

---

## 4. Market Data Tables

### 4.1 `price_history`

```sql
CREATE TABLE price_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(20) NOT NULL,
    date            DATE NOT NULL,
    open            DECIMAL(18,4),
    high            DECIMAL(18,4),
    low             DECIMAL(18,4),
    close           DECIMAL(18,4) NOT NULL,
    adj_close       DECIMAL(18,4) NOT NULL,          -- Adjusted for splits/dividends
    volume          BIGINT,
    daily_return     DECIMAL(12,8),                   -- (adj_close - prev_adj_close) / prev_adj_close
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(ticker, date)
);

CREATE INDEX idx_price_history_ticker_date ON price_history(ticker, date DESC);
CREATE INDEX idx_price_history_date ON price_history(date);
```

### 4.2 `dividends`

```sql
CREATE TABLE dividends (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(20) NOT NULL,
    ex_date         DATE NOT NULL,
    payment_date    DATE,
    amount          DECIMAL(18,6) NOT NULL,
    currency        currency_code NOT NULL DEFAULT 'USD',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(ticker, ex_date)
);

CREATE INDEX idx_dividends_ticker ON dividends(ticker);
```

### 4.3 `splits`

```sql
CREATE TABLE splits (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(20) NOT NULL,
    date            DATE NOT NULL,
    ratio           DECIMAL(10,4) NOT NULL,           -- e.g., 2.0 for 2:1 split
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(ticker, date)
);
```

### 4.4 `exchange_rates`

```sql
CREATE TABLE exchange_rates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_currency   currency_code NOT NULL,
    to_currency     currency_code NOT NULL,
    date            DATE NOT NULL,
    rate            DECIMAL(18,8) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(from_currency, to_currency, date)
);

CREATE INDEX idx_exchange_rates_pair_date
    ON exchange_rates(from_currency, to_currency, date DESC);
```

---

## 5. Analytics Tables

### 5.1 `risk_metrics`

```sql
CREATE TABLE risk_metrics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id        UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    calculation_date    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lookback_days       INTEGER NOT NULL DEFAULT 252,  -- 1 trading year
    risk_free_rate      DECIMAL(6,4) NOT NULL,

    -- Core metrics
    annualized_return   DECIMAL(12,6),
    annualized_volatility DECIMAL(12,6),
    sharpe_ratio        DECIMAL(10,6),
    sortino_ratio       DECIMAL(10,6),
    beta                DECIMAL(10,6),
    alpha               DECIMAL(10,6),                 -- Jensen's alpha
    information_ratio   DECIMAL(10,6),
    tracking_error      DECIMAL(12,6),

    -- Drawdown metrics
    max_drawdown        DECIMAL(10,6),                 -- Negative percentage
    max_drawdown_start  DATE,
    max_drawdown_end    DATE,
    current_drawdown    DECIMAL(10,6),

    -- Tail risk
    var_95              DECIMAL(12,6),                 -- 95% VaR (daily)
    var_99              DECIMAL(12,6),                 -- 99% VaR (daily)
    cvar_95             DECIMAL(12,6),                 -- 95% CVaR / Expected Shortfall
    cvar_99             DECIMAL(12,6),                 -- 99% CVaR

    -- Additional
    downside_deviation  DECIMAL(12,6),
    calmar_ratio        DECIMAL(10,6),
    skewness            DECIMAL(10,6),
    kurtosis            DECIMAL(10,6),

    -- Benchmark used
    benchmark           benchmark_type,

    -- Full return series (for charting)
    return_series       JSONB,                         -- {dates: [], values: []}
    drawdown_series     JSONB,                         -- {dates: [], values: []}

    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_risk_metrics_portfolio ON risk_metrics(portfolio_id, calculation_date DESC);
```

### 5.2 `benchmark_comparisons`

```sql
CREATE TABLE benchmark_comparisons (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id        UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    benchmark           benchmark_type NOT NULL,
    calculation_date    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lookback_days       INTEGER NOT NULL DEFAULT 252,

    -- Relative metrics
    active_return       DECIMAL(12,6),                 -- Rp - Rb
    tracking_error      DECIMAL(12,6),
    information_ratio   DECIMAL(10,6),
    alpha               DECIMAL(10,6),                 -- Jensen's alpha
    beta                DECIMAL(10,6),

    -- Capture ratios
    upside_capture      DECIMAL(10,4),                 -- Percentage (e.g., 110.0 = 110%)
    downside_capture    DECIMAL(10,4),

    -- Rolling metrics (JSONB for chart data)
    rolling_alpha       JSONB,                         -- {dates: [], values: []}
    rolling_beta        JSONB,
    rolling_correlation JSONB,

    -- Cumulative return comparison
    portfolio_cumulative JSONB,                        -- {dates: [], values: []}
    benchmark_cumulative JSONB,

    -- Period returns comparison
    period_returns      JSONB,                         -- {1m: {port, bench}, 3m: {...}, ...}

    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_benchmark_comp_portfolio
    ON benchmark_comparisons(portfolio_id, benchmark, calculation_date DESC);
```

### 5.3 `health_scores`

```sql
CREATE TABLE health_scores (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id        UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    calculation_date    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Overall
    overall_score       INTEGER NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
    overall_grade       health_grade NOT NULL,
    overall_explanation TEXT NOT NULL,

    -- Diversification subscore (25%)
    diversification_score INTEGER NOT NULL CHECK (diversification_score BETWEEN 0 AND 100),
    diversification_grade health_grade NOT NULL,
    diversification_details JSONB NOT NULL,
    -- Details: {hhi, sector_concentration, num_holdings, correlation_avg, explanation}

    -- Risk subscore (30%)
    risk_score          INTEGER NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    risk_grade          health_grade NOT NULL,
    risk_details        JSONB NOT NULL,
    -- Details: {vol_vs_benchmark, mdd_severity, var_breaches, tail_risk, explanation}

    -- Performance subscore (25%)
    performance_score   INTEGER NOT NULL CHECK (performance_score BETWEEN 0 AND 100),
    performance_grade   health_grade NOT NULL,
    performance_details JSONB NOT NULL,
    -- Details: {returns_1m, returns_3m, returns_1y, sharpe, sortino, consistency, explanation}

    -- Efficiency subscore (20%)
    efficiency_score    INTEGER NOT NULL CHECK (efficiency_score BETWEEN 0 AND 100),
    efficiency_grade    health_grade NOT NULL,
    efficiency_details  JSONB NOT NULL,
    -- Details: {sharpe_vs_benchmark, information_ratio, return_per_risk, explanation}

    -- Recommendations
    recommendations     JSONB DEFAULT '[]',            -- [{priority, category, action, rationale}]

    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_health_scores_portfolio
    ON health_scores(portfolio_id, calculation_date DESC);
```

### 5.4 `optimization_runs`

```sql
CREATE TABLE optimization_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id        UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    method              optimization_method NOT NULL,
    calculation_date    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints used
    constraints         JSONB NOT NULL DEFAULT '{}',
    -- {min_weight, max_weight, sector_limits, turnover_limit}

    -- Results
    current_weights     JSONB NOT NULL,                -- {ticker: weight, ...}
    optimal_weights     JSONB NOT NULL,                -- {ticker: weight, ...}
    expected_return     DECIMAL(12,6),
    expected_volatility DECIMAL(12,6),
    expected_sharpe     DECIMAL(10,6),

    -- Trade recommendations
    trades              JSONB NOT NULL DEFAULT '[]',
    -- [{ticker, action, current_weight, target_weight, delta}]

    -- Efficient frontier
    efficient_frontier  JSONB,
    -- {returns: [], volatilities: [], sharpe_ratios: []}

    -- Black-Litterman specific
    views               JSONB,                         -- User views if BL method
    posterior_returns    JSONB,

    status              VARCHAR(20) NOT NULL DEFAULT 'completed',
    error_message       TEXT,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_optimization_runs_portfolio
    ON optimization_runs(portfolio_id, calculation_date DESC);
```

### 5.5 `stress_test_results`

```sql
CREATE TABLE stress_test_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id        UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    scenario            stress_scenario NOT NULL,
    calculation_date    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Scenario parameters
    scenario_start_date DATE NOT NULL,
    scenario_end_date   DATE NOT NULL,
    scenario_description TEXT NOT NULL,

    -- Portfolio impact
    portfolio_return    DECIMAL(12,6) NOT NULL,
    max_drawdown        DECIMAL(12,6) NOT NULL,
    recovery_days       INTEGER,                       -- Estimated days to recover
    benchmark_return    DECIMAL(12,6),

    -- Per-holding impact
    holding_impacts     JSONB NOT NULL,
    -- [{ticker, return, contribution, weight}]

    -- Sector-level impact
    sector_impacts      JSONB NOT NULL,
    -- [{sector, return, weight, contribution}]

    -- Summary
    summary             TEXT NOT NULL,

    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stress_test_portfolio
    ON stress_test_results(portfolio_id, scenario, calculation_date DESC);
```

---

## 6. AI / Agent Tables

### 6.1 `copilot_sessions`

```sql
CREATE TABLE copilot_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    portfolio_id    UUID REFERENCES portfolios(id) ON DELETE SET NULL,
    title           VARCHAR(255),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    message_count   INTEGER NOT NULL DEFAULT 0,
    last_message_at TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_copilot_sessions_user ON copilot_sessions(user_id, created_at DESC);
```

### 6.2 `copilot_messages`

```sql
CREATE TABLE copilot_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES copilot_sessions(id) ON DELETE CASCADE,
    role            message_role NOT NULL,
    content         TEXT NOT NULL,
    agent_name      VARCHAR(100),                    -- Which agent generated this
    tool_calls      JSONB DEFAULT '[]',              -- Tool invocations
    tool_results    JSONB DEFAULT '[]',              -- Tool outputs
    citations       JSONB DEFAULT '[]',              -- [{source, data_point, value}]
    reasoning       TEXT,                            -- Chain-of-thought (stored, not shown)
    tokens_used     INTEGER DEFAULT 0,
    latency_ms      INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_copilot_messages_session ON copilot_messages(session_id, created_at);
```

---

## 7. News / Intelligence Tables

### 7.1 `news_articles`

```sql
CREATE TABLE news_articles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     VARCHAR(255) UNIQUE,              -- Source-specific ID
    source          VARCHAR(50) NOT NULL,              -- 'finnhub' | 'newsapi'
    title           TEXT NOT NULL,
    summary         TEXT,
    url             TEXT NOT NULL,
    image_url       TEXT,
    author          VARCHAR(255),
    published_at    TIMESTAMPTZ NOT NULL,
    category        VARCHAR(100),                     -- 'earnings', 'market', 'company'
    related_tickers JSONB DEFAULT '[]',               -- ['AAPL', 'MSFT']
    raw_data        JSONB DEFAULT '{}',               -- Full API response
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_news_articles_published ON news_articles(published_at DESC);
CREATE INDEX idx_news_articles_source ON news_articles(source);
CREATE INDEX idx_news_articles_tickers ON news_articles USING GIN(related_tickers);
```

### 7.2 `sentiment_scores`

```sql
CREATE TABLE sentiment_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id      UUID NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    ticker          VARCHAR(20),                      -- Which ticker this sentiment is for
    sentiment       VARCHAR(20) NOT NULL,             -- 'positive', 'negative', 'neutral'
    confidence      DECIMAL(5,4) NOT NULL,            -- 0.0000 – 1.0000
    impact_score    DECIMAL(5,4),                     -- Estimated portfolio impact
    analysis        TEXT,                             -- LLM-generated analysis
    model_used      VARCHAR(100) DEFAULT 'gemini',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sentiment_article ON sentiment_scores(article_id);
CREATE INDEX idx_sentiment_ticker ON sentiment_scores(ticker);
```

---

## 8. Reporting Table

### 8.1 `reports`

```sql
CREATE TABLE reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id    UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    report_type     report_type NOT NULL,
    title           VARCHAR(255) NOT NULL,
    file_path       TEXT,                             -- Path to generated PDF
    file_size_bytes INTEGER,
    parameters      JSONB DEFAULT '{}',               -- Generation parameters
    summary         TEXT,                             -- Executive summary text
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- status: 'pending', 'generating', 'completed', 'failed'
    error_message   TEXT,
    generated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reports_portfolio ON reports(portfolio_id, created_at DESC);
CREATE INDEX idx_reports_user ON reports(user_id, created_at DESC);
```

---

## 9. System Tables

### 9.1 `cache_entries`

```sql
CREATE TABLE cache_entries (
    key             VARCHAR(500) PRIMARY KEY,
    value           JSONB NOT NULL,
    category        VARCHAR(100) NOT NULL,            -- 'market_data', 'analytics', 'metadata'
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cache_category ON cache_entries(category);
CREATE INDEX idx_cache_expires ON cache_entries(expires_at);
```

---

## 10. Database Functions & Triggers

### 10.1 Auto-Update `updated_at`

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables with updated_at
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_portfolios_updated_at
    BEFORE UPDATE ON portfolios
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_holdings_updated_at
    BEFORE UPDATE ON holdings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_copilot_sessions_updated_at
    BEFORE UPDATE ON copilot_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cache_entries_updated_at
    BEFORE UPDATE ON cache_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 10.2 Portfolio Value Recalculation

```sql
-- Recalculate portfolio totals when holdings change
CREATE OR REPLACE FUNCTION recalculate_portfolio_totals()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE portfolios
    SET
        total_value = COALESCE((
            SELECT SUM(current_value) FROM holdings WHERE portfolio_id = COALESCE(NEW.portfolio_id, OLD.portfolio_id)
        ), 0),
        total_cost = COALESCE((
            SELECT SUM(cost_basis) FROM holdings WHERE portfolio_id = COALESCE(NEW.portfolio_id, OLD.portfolio_id)
        ), 0),
        unrealized_pnl = COALESCE((
            SELECT SUM(unrealized_pnl) FROM holdings WHERE portfolio_id = COALESCE(NEW.portfolio_id, OLD.portfolio_id)
        ), 0)
    WHERE id = COALESCE(NEW.portfolio_id, OLD.portfolio_id);

    -- Update pnl_percentage
    UPDATE portfolios
    SET pnl_percentage = CASE
        WHEN total_cost > 0 THEN (unrealized_pnl / total_cost) * 100
        ELSE 0
    END
    WHERE id = COALESCE(NEW.portfolio_id, OLD.portfolio_id);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_recalculate_portfolio
    AFTER INSERT OR UPDATE OR DELETE ON holdings
    FOR EACH ROW EXECUTE FUNCTION recalculate_portfolio_totals();
```

### 10.3 Holding Weight Recalculation

```sql
CREATE OR REPLACE FUNCTION recalculate_holding_weights()
RETURNS TRIGGER AS $$
DECLARE
    portfolio_total DECIMAL(18,4);
BEGIN
    SELECT COALESCE(SUM(current_value), 0)
    INTO portfolio_total
    FROM holdings
    WHERE portfolio_id = COALESCE(NEW.portfolio_id, OLD.portfolio_id);

    IF portfolio_total > 0 THEN
        UPDATE holdings
        SET weight = current_value / portfolio_total
        WHERE portfolio_id = COALESCE(NEW.portfolio_id, OLD.portfolio_id);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_recalculate_weights
    AFTER INSERT OR UPDATE OF current_value OR DELETE ON holdings
    FOR EACH ROW EXECUTE FUNCTION recalculate_holding_weights();
```

---

## 11. Indexes Summary

| Table                    | Index                                         | Type      | Purpose                            |
|--------------------------|-----------------------------------------------|-----------|-------------------------------------|
| `users`                  | `idx_users_email`                              | B-tree    | Login lookup                        |
| `portfolios`             | `idx_portfolios_user_id`                       | B-tree    | User's portfolios                   |
| `portfolios`             | `idx_portfolios_status`                        | B-tree    | Filter by status                    |
| `holdings`               | `idx_holdings_portfolio_id`                    | B-tree    | Portfolio's holdings                |
| `holdings`               | `idx_holdings_ticker`                          | B-tree    | Cross-portfolio ticker lookup       |
| `transactions`           | `idx_transactions_portfolio_id`                | B-tree    | Transaction history                 |
| `transactions`           | `idx_transactions_date`                        | B-tree    | Date range queries                  |
| `instruments`            | `idx_instruments_ticker`                       | B-tree    | Ticker lookup                       |
| `instruments`            | `idx_instruments_sector`                       | B-tree    | Sector analysis                     |
| `price_history`          | `idx_price_history_ticker_date`                | B-tree    | Time-series queries (covering)      |
| `risk_metrics`           | `idx_risk_metrics_portfolio`                   | B-tree    | Latest metrics per portfolio        |
| `benchmark_comparisons`  | `idx_benchmark_comp_portfolio`                 | B-tree    | Latest comparison per benchmark     |
| `health_scores`          | `idx_health_scores_portfolio`                  | B-tree    | Latest score per portfolio          |
| `news_articles`          | `idx_news_articles_tickers`                    | GIN       | JSONB array containment search      |
| `copilot_messages`       | `idx_copilot_messages_session`                 | B-tree    | Message ordering                    |

---

## 12. Migration Strategy

### Alembic Configuration

```
alembic/
├── alembic.ini
├── env.py                 # Async engine configuration
├── script.py.mako         # Migration template
└── versions/
    ├── 001_initial_schema.py
    ├── 002_add_analytics_tables.py
    ├── 003_add_agent_tables.py
    ├── 004_add_news_tables.py
    └── 005_add_reporting_tables.py
```

### Migration Naming Convention

```
{revision_number}_{description}.py

Examples:
001_initial_schema.py
002_add_risk_metrics_table.py
003_add_benchmark_comparisons.py
```

### Rollback Strategy

- Every migration includes both `upgrade()` and `downgrade()` functions
- Use `alembic downgrade -1` to revert the latest migration
- Test rollbacks in development before applying to production

---

## 13. Data Retention Policy

| Data Type          | Retention         | Notes                                  |
|-------------------|-------------------|----------------------------------------|
| Price history      | Unlimited         | Historical data essential for analytics |
| Risk metrics       | 90 days           | Keep latest + daily snapshots          |
| Benchmark data     | 90 days           | Keep latest + daily snapshots          |
| Health scores      | 90 days           | Keep latest + daily snapshots          |
| Optimization runs  | 30 days           | On-demand, not time-critical           |
| Stress test results| 30 days           | Regenerated on demand                  |
| News articles      | 90 days           | Rolling window                         |
| Copilot messages   | Unlimited         | User conversation history              |
| Cache entries      | Auto-expire       | Cleaned by TTL                         |
| Reports            | Unlimited         | User-generated artifacts               |

---

## 14. Seed Data

### Default Benchmarks

```sql
INSERT INTO instruments (ticker, name, instrument_type, exchange, currency) VALUES
    ('^NSEI',  'NIFTY 50',    'index', 'NSE',    'INR'),
    ('^BSESN', 'S&P BSE SENSEX', 'index', 'BSE', 'INR'),
    ('^GSPC',  'S&P 500',     'index', 'NYSE',   'USD'),
    ('^NDX',   'NASDAQ-100',  'index', 'NASDAQ', 'USD');
```

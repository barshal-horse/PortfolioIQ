# PortfolioIQ — API Specification

> FastAPI REST API · OpenAPI 3.1 · Pydantic v2 Schemas

---

## 1. API Overview

**Base URL**: `http://localhost:8000/api/v1`  
**Format**: JSON  
**Authentication**: JWT Bearer Token  
**Rate Limiting**: Per-user, per-endpoint category  
**Versioning**: URL path (`/api/v1/`)

### Standard Response Envelope

```json
// Success
{
    "status": "success",
    "data": { ... },
    "meta": {
        "timestamp": "2024-01-15T10:30:00Z",
        "request_id": "uuid"
    }
}

// Error
{
    "status": "error",
    "error": {
        "code": "RESOURCE_NOT_FOUND",
        "message": "Portfolio not found",
        "details": {}
    },
    "meta": {
        "timestamp": "2024-01-15T10:30:00Z",
        "request_id": "uuid"
    }
}

// Paginated
{
    "status": "success",
    "data": [ ... ],
    "meta": {
        "total": 100,
        "page": 1,
        "page_size": 20,
        "total_pages": 5,
        "timestamp": "2024-01-15T10:30:00Z"
    }
}
```

### Standard Error Codes

| HTTP Status | Error Code                | Description                        |
|-------------|---------------------------|-------------------------------------|
| 400         | `VALIDATION_ERROR`        | Invalid request body/params         |
| 400         | `INVALID_TICKER`          | Unrecognized ticker symbol          |
| 400         | `INVALID_CSV`             | Malformed CSV upload                |
| 401         | `UNAUTHORIZED`            | Missing or expired token            |
| 403         | `FORBIDDEN`               | Insufficient permissions            |
| 404         | `RESOURCE_NOT_FOUND`      | Entity not found                    |
| 409         | `DUPLICATE_RESOURCE`      | Resource already exists             |
| 422         | `UNPROCESSABLE_ENTITY`    | Semantically invalid input          |
| 429         | `RATE_LIMIT_EXCEEDED`     | Too many requests                   |
| 500         | `INTERNAL_ERROR`          | Unexpected server error             |
| 503         | `SERVICE_UNAVAILABLE`     | External service down               |

---

## 2. Authentication Endpoints

### `POST /api/v1/auth/register`

Create a new user account.

**Request Body:**
```json
{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "full_name": "John Doe",
    "base_currency": "USD"
}
```

**Validation Rules:**
- `email`: Valid email format, max 255 chars
- `password`: Min 8 chars, at least 1 uppercase, 1 lowercase, 1 digit
- `full_name`: Min 2 chars, max 255 chars
- `base_currency`: One of `USD`, `INR`, `EUR`, `GBP`

**Response (201):**
```json
{
    "status": "success",
    "data": {
        "id": "uuid",
        "email": "user@example.com",
        "full_name": "John Doe",
        "base_currency": "USD",
        "created_at": "2024-01-15T10:30:00Z"
    }
}
```

---

### `POST /api/v1/auth/login`

Authenticate and receive tokens.

**Request Body:**
```json
{
    "email": "user@example.com",
    "password": "SecurePass123!"
}
```

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "access_token": "eyJ...",
        "refresh_token": "eyJ...",
        "token_type": "bearer",
        "expires_in": 1800,
        "user": {
            "id": "uuid",
            "email": "user@example.com",
            "full_name": "John Doe"
        }
    }
}
```

---

### `POST /api/v1/auth/refresh`

Refresh an expired access token.

**Request Body:**
```json
{
    "refresh_token": "eyJ..."
}
```

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "access_token": "eyJ...",
        "token_type": "bearer",
        "expires_in": 1800
    }
}
```

---

### `GET /api/v1/auth/me`

Get current user profile.

**Headers:** `Authorization: Bearer <access_token>`

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "id": "uuid",
        "email": "user@example.com",
        "full_name": "John Doe",
        "base_currency": "USD",
        "risk_free_rate": 0.05,
        "is_active": true,
        "created_at": "2024-01-15T10:30:00Z"
    }
}
```

---

## 3. Portfolio Endpoints

### `POST /api/v1/portfolios`

Create a new portfolio.

**Request Body:**
```json
{
    "name": "My Growth Portfolio",
    "description": "Long-term equity growth strategy",
    "base_currency": "USD",
    "benchmark": "SP500"
}
```

**Validation:**
- `name`: 1–255 chars, unique per user
- `benchmark`: One of `NIFTY50`, `SENSEX`, `SP500`, `NASDAQ100`

**Response (201):**
```json
{
    "status": "success",
    "data": {
        "id": "uuid",
        "name": "My Growth Portfolio",
        "description": "Long-term equity growth strategy",
        "base_currency": "USD",
        "benchmark": "SP500",
        "status": "active",
        "total_value": 0.0,
        "total_cost": 0.0,
        "unrealized_pnl": 0.0,
        "pnl_percentage": 0.0,
        "holdings_count": 0,
        "created_at": "2024-01-15T10:30:00Z"
    }
}
```

---

### `GET /api/v1/portfolios`

List all portfolios for the authenticated user.

**Query Parameters:**
- `status` (optional): `active` | `archived` | `draft`
- `page` (optional): Page number, default 1
- `page_size` (optional): Items per page, default 20, max 100

**Response (200):**
```json
{
    "status": "success",
    "data": [
        {
            "id": "uuid",
            "name": "My Growth Portfolio",
            "status": "active",
            "benchmark": "SP500",
            "total_value": 150000.00,
            "total_cost": 120000.00,
            "unrealized_pnl": 30000.00,
            "pnl_percentage": 25.00,
            "holdings_count": 15,
            "last_analyzed": "2024-01-15T06:30:00Z",
            "created_at": "2024-01-01T10:00:00Z"
        }
    ],
    "meta": { "total": 3, "page": 1, "page_size": 20, "total_pages": 1 }
}
```

---

### `GET /api/v1/portfolios/{portfolio_id}`

Get a single portfolio with its holdings.

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "id": "uuid",
        "name": "My Growth Portfolio",
        "description": "Long-term equity growth strategy",
        "base_currency": "USD",
        "benchmark": "SP500",
        "status": "active",
        "total_value": 150000.00,
        "total_cost": 120000.00,
        "unrealized_pnl": 30000.00,
        "pnl_percentage": 25.00,
        "last_analyzed": "2024-01-15T06:30:00Z",
        "holdings": [
            {
                "id": "uuid",
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "sector": "Technology",
                "quantity": 50,
                "average_cost": 150.00,
                "current_price": 195.00,
                "current_value": 9750.00,
                "cost_basis": 7500.00,
                "unrealized_pnl": 2250.00,
                "weight": 0.065,
                "currency": "USD"
            }
        ],
        "sector_allocation": {
            "Technology": 0.35,
            "Healthcare": 0.20,
            "Financials": 0.15,
            "Consumer Discretionary": 0.15,
            "Industrials": 0.15
        },
        "created_at": "2024-01-01T10:00:00Z"
    }
}
```

---

### `PUT /api/v1/portfolios/{portfolio_id}`

Update portfolio metadata.

**Request Body:**
```json
{
    "name": "Updated Portfolio Name",
    "description": "Updated description",
    "benchmark": "NASDAQ100",
    "status": "active"
}
```

**Response (200):** Updated portfolio object.

---

### `DELETE /api/v1/portfolios/{portfolio_id}`

Delete a portfolio and all associated data.

**Response (204):** No content.

---

### `POST /api/v1/portfolios/{portfolio_id}/upload-csv`

Upload holdings via CSV file.

**Content-Type:** `multipart/form-data`

**CSV Format:**
```csv
ticker,quantity,average_cost,currency
AAPL,50,150.00,USD
MSFT,30,280.00,USD
RELIANCE.NS,100,2500.00,INR
TCS.NS,50,3500.00,INR
```

**Required Columns:** `ticker`, `quantity`, `average_cost`  
**Optional Columns:** `currency` (defaults to portfolio base currency)

**File Constraints:**
- Max size: 10 MB
- Format: `.csv` only
- Max rows: 500

**Response (201):**
```json
{
    "status": "success",
    "data": {
        "imported": 4,
        "skipped": 0,
        "errors": [],
        "holdings": [ ... ]
    }
}
```

**Error Response (partial import):**
```json
{
    "status": "success",
    "data": {
        "imported": 3,
        "skipped": 1,
        "errors": [
            {
                "row": 4,
                "ticker": "INVALIDTICKER",
                "error": "Ticker not found in any exchange"
            }
        ],
        "holdings": [ ... ]
    }
}
```

---

## 4. Holdings Endpoints

### `POST /api/v1/portfolios/{portfolio_id}/holdings`

Add a single holding manually.

**Request Body:**
```json
{
    "ticker": "GOOGL",
    "quantity": 25,
    "average_cost": 140.00,
    "currency": "USD"
}
```

**Validation:**
- `ticker`: Valid ticker (verified against yfinance), max 20 chars
- `quantity`: Positive number, max 6 decimal places
- `average_cost`: Positive number

**Response (201):** Holding object with enriched data (sector, current price, etc.)

---

### `PUT /api/v1/portfolios/{portfolio_id}/holdings/{holding_id}`

Update a holding.

**Request Body:**
```json
{
    "quantity": 30,
    "average_cost": 145.00
}
```

**Response (200):** Updated holding object.

---

### `DELETE /api/v1/portfolios/{portfolio_id}/holdings/{holding_id}`

Remove a holding from the portfolio.

**Response (204):** No content.

---

### `POST /api/v1/portfolios/{portfolio_id}/holdings/bulk`

Bulk add/update holdings.

**Request Body:**
```json
{
    "holdings": [
        { "ticker": "AAPL", "quantity": 50, "average_cost": 150.00 },
        { "ticker": "MSFT", "quantity": 30, "average_cost": 280.00 },
        { "ticker": "AMZN", "quantity": 20, "average_cost": 135.00 }
    ],
    "mode": "merge"
}
```

**Modes:**
- `merge`: Add new, update existing (by ticker)
- `replace`: Delete all existing holdings, insert new

**Response (201):**
```json
{
    "status": "success",
    "data": {
        "added": 2,
        "updated": 1,
        "deleted": 0,
        "holdings": [ ... ]
    }
}
```

---

## 5. Market Data Endpoints

### `GET /api/v1/market-data/quote/{ticker}`

Get current quote for a ticker.

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "price": 195.50,
        "change": 2.30,
        "change_percent": 1.19,
        "volume": 45000000,
        "market_cap": 3050000000000,
        "pe_ratio": 31.2,
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "currency": "USD",
        "exchange": "NASDAQ",
        "last_updated": "2024-01-15T16:00:00Z"
    }
}
```

---

### `GET /api/v1/market-data/history/{ticker}`

Get historical price data.

**Query Parameters:**
- `period` (optional): `1mo`, `3mo`, `6mo`, `1y`, `3y`, `5y`, `max` (default: `1y`)
- `interval` (optional): `1d`, `1wk`, `1mo` (default: `1d`)

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "ticker": "AAPL",
        "period": "1y",
        "interval": "1d",
        "prices": [
            {
                "date": "2024-01-15",
                "open": 193.00,
                "high": 196.50,
                "low": 192.50,
                "close": 195.50,
                "adj_close": 195.50,
                "volume": 45000000
            }
        ]
    }
}
```

---

### `GET /api/v1/portfolios/{portfolio_id}/valuation`

Get portfolio valuation time series.

**Query Parameters:**
- `period`: `1mo`, `3mo`, `6mo`, `1y`, `3y` (default: `1y`)

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "portfolio_id": "uuid",
        "current_value": 150000.00,
        "period": "1y",
        "valuation_series": [
            { "date": "2024-01-15", "value": 150000.00 },
            { "date": "2024-01-14", "value": 148500.00 }
        ],
        "total_return": 0.25,
        "total_return_amount": 30000.00
    }
}
```

---

### `GET /api/v1/portfolios/{portfolio_id}/returns`

Get daily return series.

**Query Parameters:**
- `period`: `1mo`, `3mo`, `6mo`, `1y` (default: `1y`)

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "portfolio_id": "uuid",
        "period": "1y",
        "returns": [
            { "date": "2024-01-15", "daily_return": 0.0119 },
            { "date": "2024-01-14", "daily_return": -0.0032 }
        ],
        "cumulative_return": 0.25,
        "annualized_return": 0.28
    }
}
```

---

## 6. Risk Analytics Endpoints

### `GET /api/v1/portfolios/{portfolio_id}/risk`

Get full risk analysis.

**Query Parameters:**
- `lookback_days` (optional): `30`, `60`, `90`, `180`, `252`, `504` (default: `252`)
- `benchmark` (optional): Override portfolio default benchmark
- `risk_free_rate` (optional): Override user default (decimal, e.g., `0.05`)

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "portfolio_id": "uuid",
        "calculation_date": "2024-01-15T10:30:00Z",
        "lookback_days": 252,
        "risk_free_rate": 0.05,
        "benchmark": "SP500",
        "metrics": {
            "annualized_return": 0.2834,
            "annualized_volatility": 0.1856,
            "sharpe_ratio": 1.2567,
            "sortino_ratio": 1.8934,
            "beta": 1.1245,
            "alpha": 0.0523,
            "information_ratio": 0.7834,
            "tracking_error": 0.0667,
            "max_drawdown": -0.1245,
            "max_drawdown_start": "2024-03-15",
            "max_drawdown_end": "2024-04-02",
            "current_drawdown": -0.0234,
            "var_95": -0.0198,
            "var_99": -0.0312,
            "cvar_95": -0.0267,
            "cvar_99": -0.0401,
            "downside_deviation": 0.1312,
            "calmar_ratio": 2.2756,
            "skewness": -0.3456,
            "kurtosis": 4.1234
        },
        "return_series": {
            "dates": ["2024-01-15", "2024-01-14"],
            "values": [0.0119, -0.0032]
        },
        "drawdown_series": {
            "dates": ["2024-01-15", "2024-01-14"],
            "values": [-0.0234, -0.0353]
        }
    }
}
```

---

### `GET /api/v1/portfolios/{portfolio_id}/risk/var`

Get detailed VaR analysis.

**Query Parameters:**
- `method` (optional): `historical`, `parametric`, `monte_carlo` (default: `historical`)
- `confidence` (optional): `0.95`, `0.99` (default: `0.95`)
- `horizon_days` (optional): `1`, `5`, `10`, `21` (default: `1`)

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "method": "historical",
        "confidence": 0.95,
        "horizon_days": 1,
        "var": -0.0198,
        "var_amount": -2970.00,
        "cvar": -0.0267,
        "cvar_amount": -4005.00,
        "portfolio_value": 150000.00,
        "interpretation": "There is a 5% probability that the portfolio could lose more than $2,970 (1.98%) in a single day."
    }
}
```

---

### `GET /api/v1/portfolios/{portfolio_id}/risk/contributions`

Get per-holding risk contribution.

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "portfolio_volatility": 0.1856,
        "contributions": [
            {
                "ticker": "AAPL",
                "weight": 0.065,
                "individual_volatility": 0.2345,
                "marginal_contribution": 0.0152,
                "percentage_contribution": 8.19,
                "beta_to_portfolio": 1.23
            }
        ]
    }
}
```

---

## 7. Benchmark Analytics Endpoints

### `GET /api/v1/portfolios/{portfolio_id}/benchmark`

Get benchmark comparison.

**Query Parameters:**
- `benchmark` (optional): Override default benchmark
- `lookback_days` (optional): Default `252`

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "portfolio_id": "uuid",
        "benchmark": "SP500",
        "calculation_date": "2024-01-15T10:30:00Z",
        "lookback_days": 252,
        "metrics": {
            "active_return": 0.0523,
            "tracking_error": 0.0667,
            "information_ratio": 0.7834,
            "alpha": 0.0523,
            "beta": 1.1245,
            "upside_capture": 112.50,
            "downside_capture": 95.30
        },
        "period_returns": {
            "1m": { "portfolio": 0.0345, "benchmark": 0.0290 },
            "3m": { "portfolio": 0.0834, "benchmark": 0.0712 },
            "6m": { "portfolio": 0.1567, "benchmark": 0.1340 },
            "1y": { "portfolio": 0.2834, "benchmark": 0.2311 },
            "ytd": { "portfolio": 0.0456, "benchmark": 0.0398 }
        },
        "cumulative_comparison": {
            "dates": ["2024-01-15", "2024-01-14"],
            "portfolio": [1.2834, 1.2715],
            "benchmark": [1.2311, 1.2289]
        },
        "rolling_alpha": {
            "dates": ["2024-01-15"],
            "values": [0.0523]
        },
        "rolling_beta": {
            "dates": ["2024-01-15"],
            "values": [1.1245]
        }
    }
}
```

---

### `GET /api/v1/benchmarks`

List available benchmarks with current data.

**Response (200):**
```json
{
    "status": "success",
    "data": [
        {
            "id": "SP500",
            "name": "S&P 500",
            "ticker": "^GSPC",
            "currency": "USD",
            "current_value": 5890.23,
            "ytd_return": 0.0398,
            "1y_return": 0.2311
        },
        {
            "id": "NIFTY50",
            "name": "NIFTY 50",
            "ticker": "^NSEI",
            "currency": "INR",
            "current_value": 22456.80,
            "ytd_return": 0.0567,
            "1y_return": 0.1890
        }
    ]
}
```

---

## 8. Health Score Endpoints

### `GET /api/v1/portfolios/{portfolio_id}/health`

Get portfolio health score with subscores and explanations.

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "portfolio_id": "uuid",
        "calculation_date": "2024-01-15T10:30:00Z",
        "overall": {
            "score": 72,
            "grade": "good",
            "explanation": "Your portfolio shows good overall health with strong performance but could improve diversification. The risk levels are within acceptable bounds for your benchmark."
        },
        "subscores": {
            "diversification": {
                "score": 58,
                "grade": "fair",
                "weight": 0.25,
                "details": {
                    "hhi": 0.0845,
                    "sector_concentration": "Technology overweight at 35%",
                    "num_holdings": 15,
                    "correlation_avg": 0.42,
                    "explanation": "Portfolio is moderately concentrated. Top 3 holdings represent 28% of value. Technology sector is significantly overweight compared to the S&P 500 benchmark (35% vs 28%). Consider adding exposure to defensive sectors like Utilities or Consumer Staples."
                }
            },
            "risk": {
                "score": 68,
                "grade": "good",
                "weight": 0.30,
                "details": {
                    "vol_vs_benchmark": 1.15,
                    "mdd_severity": "moderate",
                    "var_breaches": 3,
                    "tail_risk": "low",
                    "explanation": "Portfolio volatility is 15% higher than the benchmark, which is acceptable for a growth portfolio. Maximum drawdown of 12.45% is within normal range. VaR at 95% confidence suggests daily losses are unlikely to exceed 1.98%."
                }
            },
            "performance": {
                "score": 85,
                "grade": "excellent",
                "weight": 0.25,
                "details": {
                    "returns_1m": 0.0345,
                    "returns_3m": 0.0834,
                    "returns_1y": 0.2834,
                    "sharpe": 1.2567,
                    "sortino": 1.8934,
                    "consistency": "high",
                    "explanation": "Portfolio has delivered strong absolute and risk-adjusted returns. Sharpe ratio of 1.26 indicates good risk-adjusted performance. Returns have been consistent with limited periods of underperformance."
                }
            },
            "efficiency": {
                "score": 78,
                "grade": "good",
                "weight": 0.20,
                "details": {
                    "sharpe_vs_benchmark": 1.12,
                    "information_ratio": 0.7834,
                    "return_per_risk": 1.53,
                    "explanation": "Portfolio Sharpe ratio exceeds the benchmark by 12%, demonstrating efficient use of risk budget. Information ratio of 0.78 suggests consistent alpha generation."
                }
            }
        },
        "recommendations": [
            {
                "priority": "high",
                "category": "diversification",
                "action": "Reduce Technology sector concentration",
                "rationale": "Technology allocation of 35% significantly exceeds benchmark weight of 28%. Consider trimming positions or adding non-tech exposure."
            },
            {
                "priority": "medium",
                "category": "risk",
                "action": "Consider hedging tail risk",
                "rationale": "While current risk levels are acceptable, adding a small allocation to low-correlation assets could reduce portfolio drawdown risk."
            }
        ]
    }
}
```

---

### `POST /api/v1/portfolios/{portfolio_id}/health/refresh`

Force recalculation of health score.

**Response (202):**
```json
{
    "status": "success",
    "data": {
        "message": "Health score recalculation started",
        "estimated_time_seconds": 5
    }
}
```

---

## 9. Optimization Endpoints

### `POST /api/v1/portfolios/{portfolio_id}/optimize`

Run portfolio optimization.

**Request Body:**
```json
{
    "method": "max_sharpe",
    "constraints": {
        "min_weight": 0.02,
        "max_weight": 0.25,
        "sector_limits": {
            "Technology": 0.35,
            "Financials": 0.25
        },
        "turnover_limit": 0.30
    },
    "lookback_days": 252,
    "risk_free_rate": 0.05
}
```

**Methods:** `mean_variance`, `max_sharpe`, `min_variance`, `risk_parity`, `black_litterman`

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "id": "uuid",
        "method": "max_sharpe",
        "calculation_date": "2024-01-15T10:30:00Z",
        "current_allocation": {
            "AAPL": 0.065,
            "MSFT": 0.080,
            "GOOGL": 0.055
        },
        "optimal_allocation": {
            "AAPL": 0.085,
            "MSFT": 0.120,
            "GOOGL": 0.045
        },
        "expected_metrics": {
            "expected_return": 0.3145,
            "expected_volatility": 0.1723,
            "expected_sharpe": 1.5345
        },
        "current_metrics": {
            "expected_return": 0.2834,
            "expected_volatility": 0.1856,
            "expected_sharpe": 1.2567
        },
        "trades": [
            {
                "ticker": "AAPL",
                "action": "buy",
                "current_weight": 0.065,
                "target_weight": 0.085,
                "delta": 0.020,
                "estimated_amount": 3000.00
            },
            {
                "ticker": "GOOGL",
                "action": "sell",
                "current_weight": 0.055,
                "target_weight": 0.045,
                "delta": -0.010,
                "estimated_amount": -1500.00
            }
        ],
        "efficient_frontier": {
            "returns": [0.10, 0.15, 0.20, 0.25, 0.30, 0.35],
            "volatilities": [0.08, 0.10, 0.13, 0.16, 0.19, 0.23],
            "sharpe_ratios": [0.63, 0.95, 1.15, 1.25, 1.32, 1.30],
            "current_position": { "return": 0.2834, "volatility": 0.1856 },
            "optimal_position": { "return": 0.3145, "volatility": 0.1723 }
        }
    }
}
```

---

### `POST /api/v1/portfolios/{portfolio_id}/optimize/black-litterman`

Run Black-Litterman optimization with user views.

**Request Body:**
```json
{
    "views": [
        {
            "type": "absolute",
            "ticker": "AAPL",
            "expected_return": 0.15,
            "confidence": 0.8
        },
        {
            "type": "relative",
            "long_ticker": "MSFT",
            "short_ticker": "GOOGL",
            "expected_outperformance": 0.05,
            "confidence": 0.6
        }
    ],
    "constraints": {
        "min_weight": 0.02,
        "max_weight": 0.25
    }
}
```

**Response (200):** Same structure as optimization response with additional `posterior_returns` field.

---

## 10. Stress Testing Endpoints

### `POST /api/v1/portfolios/{portfolio_id}/stress-test`

Run stress test scenarios.

**Request Body:**
```json
{
    "scenarios": ["gfc_2008", "covid_2020", "high_inflation_2022", "rate_shock_2022"]
}
```

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "portfolio_id": "uuid",
        "calculation_date": "2024-01-15T10:30:00Z",
        "scenarios": [
            {
                "scenario": "gfc_2008",
                "description": "Global Financial Crisis (Sep 2008 – Mar 2009)",
                "scenario_start": "2008-09-15",
                "scenario_end": "2009-03-09",
                "portfolio_return": -0.4523,
                "max_drawdown": -0.5234,
                "benchmark_return": -0.4689,
                "recovery_days": 420,
                "holding_impacts": [
                    {
                        "ticker": "AAPL",
                        "return": -0.5678,
                        "weight": 0.065,
                        "contribution": -0.0369
                    }
                ],
                "sector_impacts": [
                    {
                        "sector": "Technology",
                        "return": -0.4234,
                        "weight": 0.35,
                        "contribution": -0.1482
                    },
                    {
                        "sector": "Financials",
                        "return": -0.6789,
                        "weight": 0.15,
                        "contribution": -0.1018
                    }
                ],
                "summary": "During the 2008 Global Financial Crisis, this portfolio would have declined 45.23%, slightly outperforming the S&P 500's 46.89% decline. The heaviest losses would come from the Financial sector. Recovery to pre-crisis levels would take approximately 420 trading days."
            }
        ]
    }
}
```

---

### `GET /api/v1/stress-test/scenarios`

List available stress test scenarios.

**Response (200):**
```json
{
    "status": "success",
    "data": [
        {
            "id": "gfc_2008",
            "name": "2008 Global Financial Crisis",
            "start_date": "2008-09-15",
            "end_date": "2009-03-09",
            "sp500_return": -0.4689,
            "description": "Collapse of Lehman Brothers triggered a global financial meltdown."
        },
        {
            "id": "covid_2020",
            "name": "COVID-19 Market Crash",
            "start_date": "2020-02-19",
            "end_date": "2020-03-23",
            "sp500_return": -0.3389,
            "description": "Pandemic-driven market sell-off with the fastest bear market in history."
        },
        {
            "id": "high_inflation_2022",
            "name": "2022 Inflation Regime",
            "start_date": "2022-01-03",
            "end_date": "2022-10-12",
            "sp500_return": -0.2510,
            "description": "Rising inflation led to aggressive Fed rate hikes and market declines."
        },
        {
            "id": "rate_shock_2022",
            "name": "Interest Rate Shock",
            "start_date": "2022-03-16",
            "end_date": "2023-07-26",
            "sp500_return": -0.0820,
            "description": "Fastest Fed rate hike cycle in decades from 0.25% to 5.50%."
        }
    ]
}
```

---

## 11. AI Copilot Endpoints

### `POST /api/v1/copilot/sessions`

Create a new copilot conversation.

**Request Body:**
```json
{
    "portfolio_id": "uuid",
    "title": "Risk Analysis Discussion"
}
```

**Response (201):**
```json
{
    "status": "success",
    "data": {
        "id": "uuid",
        "portfolio_id": "uuid",
        "title": "Risk Analysis Discussion",
        "created_at": "2024-01-15T10:30:00Z"
    }
}
```

---

### `GET /api/v1/copilot/sessions`

List conversation sessions.

**Response (200):** Array of session objects.

---

### `POST /api/v1/copilot/sessions/{session_id}/messages`

Send a message and get AI response.

**Request Body:**
```json
{
    "content": "What are the biggest risks in my portfolio right now?"
}
```

**Response (200):** (Non-streaming)
```json
{
    "status": "success",
    "data": {
        "user_message": {
            "id": "uuid",
            "role": "user",
            "content": "What are the biggest risks in my portfolio right now?",
            "created_at": "2024-01-15T10:30:00Z"
        },
        "assistant_message": {
            "id": "uuid",
            "role": "assistant",
            "content": "Based on my analysis of your portfolio...",
            "agent_name": "risk_agent",
            "citations": [
                {
                    "source": "risk_metrics",
                    "data_point": "Sharpe Ratio",
                    "value": 1.26
                }
            ],
            "created_at": "2024-01-15T10:30:05Z"
        }
    }
}
```

---

### `POST /api/v1/copilot/sessions/{session_id}/messages/stream`

Send a message with streaming response (SSE).

**Request Body:** Same as non-streaming.

**Response:** `text/event-stream`
```
data: {"type": "thinking", "agent": "copilot_router", "content": "Routing to risk_agent..."}

data: {"type": "tool_call", "agent": "risk_agent", "tool": "get_risk_metrics", "args": {"portfolio_id": "uuid"}}

data: {"type": "token", "content": "Based "}
data: {"type": "token", "content": "on my "}
data: {"type": "token", "content": "analysis..."}

data: {"type": "citation", "source": "risk_metrics", "data_point": "Sharpe Ratio", "value": 1.26}

data: {"type": "done", "message_id": "uuid"}
```

---

### `GET /api/v1/copilot/sessions/{session_id}/messages`

Get conversation history.

**Query Parameters:**
- `page` (optional): Default 1
- `page_size` (optional): Default 50

**Response (200):** Array of message objects.

---

## 12. News Intelligence Endpoints

### `GET /api/v1/portfolios/{portfolio_id}/news`

Get news for portfolio holdings.

**Query Parameters:**
- `days` (optional): Lookback days, default 7, max 30
- `category` (optional): `all`, `earnings`, `company`, `market`
- `sentiment` (optional): `all`, `positive`, `negative`, `neutral`
- `page`, `page_size`

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "articles": [
            {
                "id": "uuid",
                "title": "Apple Reports Record Q4 Revenue",
                "summary": "Apple Inc. reported quarterly revenue of $89.5 billion...",
                "url": "https://...",
                "source": "finnhub",
                "published_at": "2024-01-15T14:00:00Z",
                "related_tickers": ["AAPL"],
                "sentiment": {
                    "label": "positive",
                    "confidence": 0.89,
                    "impact_score": 0.72
                },
                "category": "earnings"
            }
        ],
        "summary": {
            "total_articles": 24,
            "sentiment_breakdown": {
                "positive": 12,
                "negative": 5,
                "neutral": 7
            },
            "top_tickers_mentioned": [
                { "ticker": "AAPL", "count": 8, "avg_sentiment": 0.72 },
                { "ticker": "MSFT", "count": 5, "avg_sentiment": 0.65 }
            ]
        }
    }
}
```

---

### `GET /api/v1/news/sentiment/{ticker}`

Get sentiment analysis for a specific ticker.

**Query Parameters:**
- `days` (optional): Default 7

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "ticker": "AAPL",
        "period_days": 7,
        "overall_sentiment": "positive",
        "sentiment_score": 0.72,
        "article_count": 8,
        "breakdown": {
            "positive": 5,
            "negative": 1,
            "neutral": 2
        },
        "trend": "improving"
    }
}
```

---

## 13. Reporting Endpoints

### `POST /api/v1/portfolios/{portfolio_id}/reports`

Generate a report.

**Request Body:**
```json
{
    "report_type": "full_portfolio",
    "title": "Q4 2024 Portfolio Report",
    "parameters": {
        "include_charts": true,
        "include_recommendations": true,
        "lookback_period": "1y"
    }
}
```

**Response (202):**
```json
{
    "status": "success",
    "data": {
        "id": "uuid",
        "report_type": "full_portfolio",
        "status": "generating",
        "estimated_time_seconds": 10
    }
}
```

---

### `GET /api/v1/reports/{report_id}`

Get report status and metadata.

**Response (200):**
```json
{
    "status": "success",
    "data": {
        "id": "uuid",
        "report_type": "full_portfolio",
        "title": "Q4 2024 Portfolio Report",
        "status": "completed",
        "file_size_bytes": 245000,
        "generated_at": "2024-01-15T10:30:10Z",
        "download_url": "/api/v1/reports/uuid/download"
    }
}
```

---

### `GET /api/v1/reports/{report_id}/download`

Download the generated PDF.

**Response:** `application/pdf` binary stream.

---

### `GET /api/v1/portfolios/{portfolio_id}/reports`

List reports for a portfolio.

**Response (200):** Array of report objects.

---

## 14. System Endpoints

### `GET /api/v1/health`

Basic health check.

```json
{ "status": "ok", "timestamp": "2024-01-15T10:30:00Z" }
```

### `GET /api/v1/health/ready`

Readiness probe (checks DB connection).

```json
{
    "status": "ok",
    "checks": {
        "database": "connected",
        "qdrant": "connected"
    }
}
```

### `GET /api/v1/health/detailed`

Full system status.

```json
{
    "status": "ok",
    "version": "1.0.0",
    "checks": {
        "database": { "status": "connected", "latency_ms": 5 },
        "qdrant": { "status": "connected", "latency_ms": 12 },
        "yfinance": { "status": "available", "latency_ms": 230 },
        "gemini": { "status": "available", "latency_ms": 450 }
    }
}
```

---

## 15. Rate Limiting Configuration

| Endpoint Category     | Limit         | Window |
|----------------------|---------------|--------|
| Auth                 | 10 req        | 1 min  |
| Portfolio CRUD       | 100 req       | 1 min  |
| Market Data          | 30 req        | 1 min  |
| Risk Analytics       | 20 req        | 1 min  |
| Benchmark Analytics  | 20 req        | 1 min  |
| Health Score         | 20 req        | 1 min  |
| Optimization         | 10 req        | 1 min  |
| Stress Testing       | 10 req        | 1 min  |
| AI Copilot           | 10 req        | 1 min  |
| News                 | 20 req        | 1 min  |
| Reports              | 5 req         | 1 min  |
| CSV Upload           | 5 req         | 1 min  |

---

## 16. Pydantic Schema Reference

### Core Schemas

```python
# Portfolio
class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    base_currency: CurrencyCode = CurrencyCode.USD
    benchmark: BenchmarkType = BenchmarkType.SP500

class PortfolioResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    base_currency: CurrencyCode
    benchmark: BenchmarkType
    status: PortfolioStatus
    total_value: Decimal
    total_cost: Decimal
    unrealized_pnl: Decimal
    pnl_percentage: Decimal
    holdings_count: int
    last_analyzed: datetime | None
    created_at: datetime

# Holding
class HoldingCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=20, pattern=r'^[A-Z0-9\.\-\^]+$')
    quantity: Decimal = Field(gt=0)
    average_cost: Decimal = Field(gt=0)
    currency: CurrencyCode = CurrencyCode.USD

class HoldingResponse(BaseModel):
    id: UUID
    ticker: str
    name: str
    sector: str | None
    quantity: Decimal
    average_cost: Decimal
    current_price: Decimal
    current_value: Decimal
    cost_basis: Decimal
    unrealized_pnl: Decimal
    weight: Decimal
    currency: CurrencyCode

# Risk Metrics
class RiskMetricsResponse(BaseModel):
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    beta: float
    alpha: float
    information_ratio: float
    tracking_error: float
    max_drawdown: float
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    downside_deviation: float
    calmar_ratio: float
    skewness: float
    kurtosis: float

# Health Score
class HealthScoreResponse(BaseModel):
    overall: ScoreDetail
    subscores: SubscoreBreakdown
    recommendations: list[Recommendation]

class ScoreDetail(BaseModel):
    score: int = Field(ge=0, le=100)
    grade: HealthGrade
    explanation: str

class Recommendation(BaseModel):
    priority: Literal["high", "medium", "low"]
    category: str
    action: str
    rationale: str
```

# PortfolioIQ — LangGraph Multi-Agent Architecture

> LangGraph 0.2+ · Google Gemini API · Qdrant Vector DB · 12 Specialized Agents

---

## 1. Architecture Overview

PortfolioIQ uses a **supervisor-worker** agent architecture built on LangGraph. A central Copilot Router classifies user intent, dispatches queries to one or more specialized agents, aggregates their outputs, and synthesizes a final response with citations and guardrails.

```
                         ┌─────────────────────┐
                         │     User Query       │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Copilot Router     │
                         │   (Supervisor Node)  │
                         │                     │
                         │  • Intent classify  │
                         │  • Agent selection  │
                         │  • Multi-agent plan │
                         └──────────┬──────────┘
                                    │
              ┌──────────┬──────────┼──────────┬──────────┐
              ▼          ▼          ▼          ▼          ▼
         ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
         │  Risk   │ │Benchmark│ │ Health  │ │ Optim.  │ │ Stress  │
         │  Agent  │ │  Agent  │ │  Agent  │ │  Agent  │ │  Agent  │
         └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
              │          │          │          │          │
              │   ┌──────┴──────┐  │   ┌──────┴──────┐  │
              │   │             │  │   │             │  │
              ▼   ▼             ▼  ▼   ▼             ▼  ▼
         ┌─────────┐       ┌─────────┐       ┌─────────┐
         │  News   │       │Diversif.│       │ Perform.│
         │  Agent  │       │  Agent  │       │  Agent  │
         └─────────┘       └─────────┘       └─────────┘
         ┌─────────┐       ┌─────────┐       ┌─────────┐
         │Sentiment│       │Reporting│       │  Goal   │
         │  Agent  │       │  Agent  │       │ Planning│
         └─────────┘       └─────────┘       └─────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  Response Synth.     │
                         │                     │
                         │  • Merge results    │
                         │  • Add citations    │
                         │  • Apply guardrails │
                         │  • Format output    │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Stream to User     │
                         └─────────────────────┘
```

---

## 2. LangGraph State Machine

### 2.1 Global State Definition

```python
from typing import Annotated, Literal, TypedDict
from langgraph.graph import StateGraph
from langchain_core.messages import BaseMessage
import operator

class AgentResult(TypedDict):
    agent_name: str
    content: str
    citations: list[dict]
    tool_calls: list[dict]
    confidence: float
    error: str | None

class CopilotState(TypedDict):
    """Global state shared across all nodes in the graph."""

    # User context
    user_id: str
    portfolio_id: str
    session_id: str

    # Conversation
    messages: Annotated[list[BaseMessage], operator.add]

    # Router decisions
    intent: str                                    # Classified intent
    selected_agents: list[str]                     # Which agents to invoke
    routing_reasoning: str                         # Why these agents

    # Agent execution
    agent_results: Annotated[list[AgentResult], operator.add]
    current_agent: str | None                      # Currently executing agent
    agents_completed: list[str]                    # Finished agents

    # Final output
    final_response: str | None
    citations: list[dict]
    guardrail_flags: list[str]

    # Control flow
    error: str | None
    should_continue: bool
    iteration_count: int                           # Prevent infinite loops
    max_iterations: int                            # Default: 5
```

### 2.2 Graph Structure

```python
from langgraph.graph import StateGraph, END

# Build the graph
graph = StateGraph(CopilotState)

# Add nodes
graph.add_node("router", copilot_router)
graph.add_node("risk_agent", risk_agent_node)
graph.add_node("benchmark_agent", benchmark_agent_node)
graph.add_node("health_agent", health_agent_node)
graph.add_node("optimization_agent", optimization_agent_node)
graph.add_node("stress_testing_agent", stress_testing_agent_node)
graph.add_node("news_agent", news_agent_node)
graph.add_node("diversification_agent", diversification_agent_node)
graph.add_node("sentiment_agent", sentiment_agent_node)
graph.add_node("performance_agent", performance_agent_node)
graph.add_node("goal_planning_agent", goal_planning_agent_node)
graph.add_node("reporting_agent", reporting_agent_node)
graph.add_node("synthesizer", response_synthesizer)
graph.add_node("guardrails", guardrails_node)

# Set entry point
graph.set_entry_point("router")

# Router dispatches to agents
graph.add_conditional_edges(
    "router",
    route_to_agents,          # Returns list of next nodes
    {
        "risk_agent": "risk_agent",
        "benchmark_agent": "benchmark_agent",
        "health_agent": "health_agent",
        "optimization_agent": "optimization_agent",
        "stress_testing_agent": "stress_testing_agent",
        "news_agent": "news_agent",
        "diversification_agent": "diversification_agent",
        "sentiment_agent": "sentiment_agent",
        "performance_agent": "performance_agent",
        "goal_planning_agent": "goal_planning_agent",
        "reporting_agent": "reporting_agent",
        "synthesizer": "synthesizer",              # Direct response (no agent needed)
    }
)

# All agents → synthesizer
for agent in AGENT_NODES:
    graph.add_edge(agent, "synthesizer")

# Synthesizer → guardrails → END
graph.add_edge("synthesizer", "guardrails")
graph.add_edge("guardrails", END)

# Compile
app = graph.compile()
```

### 2.3 Graph Visualization

```
                    ┌────────────────┐
                    │    START       │
                    └───────┬────────┘
                            │
                            ▼
                    ┌────────────────┐
                    │    Router      │
                    └───────┬────────┘
                            │
            ┌───────┬───────┼───────┬───────┐
            │       │       │       │       │
            ▼       ▼       ▼       ▼       ▼
         ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐
         │Risk  ││Bench.││Health││Optim.││...   │ (Parallel execution)
         │Agent ││Agent ││Agent ││Agent ││      │
         └──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘
            │       │       │       │       │
            └───────┴───────┼───────┴───────┘
                            │
                            ▼
                    ┌────────────────┐
                    │  Synthesizer   │
                    └───────┬────────┘
                            │
                            ▼
                    ┌────────────────┐
                    │  Guardrails    │
                    └───────┬────────┘
                            │
                            ▼
                    ┌────────────────┐
                    │      END       │
                    └────────────────┘
```

---

## 3. Agent Registry

### 3.1 Complete Agent Catalog

| Agent                    | ID                        | Purpose                                          | Tools                                  |
|--------------------------|---------------------------|--------------------------------------------------|----------------------------------------|
| **Copilot Router**       | `copilot_router`          | Intent classification, agent dispatch            | None (routing only)                    |
| **Risk Agent**           | `risk_agent`              | Volatility, Sharpe, VaR, drawdown analysis       | `get_risk_metrics`, `get_var_analysis`, `get_risk_contributions` |
| **Benchmark Agent**      | `benchmark_agent`         | Benchmark comparison, relative performance       | `get_benchmark_comparison`, `get_capture_ratios`, `get_benchmark_list` |
| **Health Agent**         | `health_agent`            | Portfolio health scoring, recommendations        | `get_health_score`, `get_subscores`    |
| **Optimization Agent**   | `optimization_agent`      | Portfolio optimization, allocation suggestions   | `run_optimization`, `get_efficient_frontier` |
| **Stress Testing Agent** | `stress_testing_agent`    | Scenario analysis, crisis simulations            | `run_stress_test`, `get_scenarios`     |
| **News Agent**           | `news_agent`              | Holdings news, earnings, market events           | `get_portfolio_news`, `get_ticker_news` |
| **Diversification Agent**| `diversification_agent`   | Concentration risk, sector analysis              | `get_concentration_metrics`, `get_correlation_matrix` |
| **Sentiment Agent**      | `sentiment_agent`         | News sentiment scoring, trend analysis           | `get_sentiment`, `get_sentiment_trend` |
| **Performance Agent**    | `performance_agent`       | Return attribution, sources of return            | `get_performance_attribution`, `get_period_returns` |
| **Goal Planning Agent**  | `goal_planning_agent`     | Retirement planning, wealth projections          | `run_goal_simulation`, `get_projections` |
| **Reporting Agent**      | `reporting_agent`         | Report generation, summary creation              | `generate_report`, `get_report_status` |

---

## 4. Copilot Router (Supervisor)

### 4.1 Intent Classification

The router uses Gemini to classify user intent into one or more agent categories.

```python
ROUTER_SYSTEM_PROMPT = """You are the PortfolioIQ Copilot Router. Your job is to:
1. Understand the user's question about their portfolio
2. Determine which specialized agent(s) should handle the query
3. Extract relevant parameters

Available agents and their capabilities:

- risk_agent: Portfolio risk metrics (volatility, Sharpe ratio, Sortino ratio, beta, alpha,
  information ratio, tracking error, max drawdown, VaR, CVaR). Use for questions about
  risk, safety, downside, worst case.

- benchmark_agent: Performance vs benchmarks (Nifty50, Sensex, S&P500, Nasdaq100).
  Active return, tracking error, capture ratios. Use for questions about how portfolio
  compares to market/indices.

- health_agent: Portfolio health score (0-100), diversification, risk, performance, and
  efficiency subscores. Use for overall portfolio assessment, grades, health checks.

- optimization_agent: Portfolio optimization (Mean-Variance, Max Sharpe, Min Variance,
  Risk Parity, Black-Litterman). Use for questions about improving allocation, rebalancing,
  optimal weights.

- stress_testing_agent: Historical crisis scenarios (2008 GFC, COVID, inflation, rate shock).
  Use for "what if" and stress/scenario questions.

- news_agent: Holdings-related news, earnings, market events. Use for news, events,
  and recent developments.

- diversification_agent: Concentration risk, sector analysis, HHI, correlation matrix.
  Use for diversification questions, concentration concerns.

- sentiment_agent: News sentiment analysis, sentiment trends. Use for questions about
  market sentiment, news tone, opinion.

- performance_agent: Return attribution, sources of return (Brinson-style). Use for
  questions about what drove performance, attribution analysis.

- goal_planning_agent: Retirement planning, wealth projections, goal probability.
  Use for financial goal and planning questions.

- reporting_agent: Generate PDF reports, summaries. Use when user asks to create
  or download a report.

RULES:
- Select 1-3 agents maximum per query
- For complex queries, select multiple agents
- For simple greetings or off-topic, return empty agent list
- Always provide reasoning for your selection

Respond in JSON format:
{
    "intent": "brief description of user intent",
    "agents": ["agent_name_1", "agent_name_2"],
    "reasoning": "why these agents",
    "parameters": {
        "lookback_days": 252,
        "benchmark": "SP500"
    }
}
"""
```

### 4.2 Intent → Agent Mapping Examples

| User Query | Classified Intent | Agents Selected |
|---|---|---|
| "What is my Sharpe ratio?" | risk_metrics | `risk_agent` |
| "How am I doing vs the S&P 500?" | benchmark_comparison | `benchmark_agent` |
| "Is my portfolio healthy?" | health_assessment | `health_agent` |
| "How can I improve my returns?" | optimization | `optimization_agent`, `health_agent` |
| "What would happen in a 2008-like crash?" | stress_testing | `stress_testing_agent` |
| "Any news about my holdings?" | news_lookup | `news_agent` |
| "Am I too concentrated in tech?" | diversification | `diversification_agent` |
| "What's the market sentiment for AAPL?" | sentiment | `sentiment_agent` |
| "Why did my portfolio underperform?" | attribution | `performance_agent`, `benchmark_agent` |
| "Can I retire in 20 years?" | goal_planning | `goal_planning_agent` |
| "Generate a full report" | reporting | `reporting_agent` |
| "Give me a complete portfolio review" | comprehensive | `health_agent`, `risk_agent`, `benchmark_agent` |

---

## 5. Specialized Agent Definitions

### 5.1 Risk Agent

```python
RISK_AGENT_PROMPT = """You are the PortfolioIQ Risk Analysis Agent. You specialize in
quantitative risk assessment of investment portfolios.

Your capabilities:
- Calculate and explain: Volatility, Sharpe Ratio, Sortino Ratio, Beta, Alpha,
  Information Ratio, Tracking Error, Maximum Drawdown, VaR, CVaR
- Compare risk levels to benchmarks
- Identify risk concentrations
- Provide risk-level interpretations (e.g., "a Sharpe of 1.5 is excellent")

IMPORTANT RULES:
1. Always cite specific numbers from your tools
2. Explain metrics in plain English after presenting numbers
3. NEVER recommend specific securities to buy or sell
4. Include the disclaimer: "This analysis is informational only and does not
   constitute financial advice."
5. Use institutional definitions — do not simplify or approximate formulas
6. When presenting VaR, always specify the confidence level and time horizon

INTERPRETATION GUIDELINES:
- Sharpe Ratio: <0 = Poor, 0-0.5 = Below average, 0.5-1.0 = Good, 1.0-2.0 = Very good, >2.0 = Excellent
- Beta: <0.8 = Defensive, 0.8-1.2 = Market-like, >1.2 = Aggressive
- Max Drawdown: 0-10% = Low, 10-20% = Moderate, 20-30% = High, >30% = Severe
- VaR 95%: Contextualize with dollar amount based on portfolio size
"""

RISK_AGENT_TOOLS = [
    "get_risk_metrics",       # Full risk metrics for portfolio
    "get_var_analysis",       # Detailed VaR breakdown
    "get_risk_contributions", # Per-holding risk contribution
    "get_portfolio_summary",  # Basic portfolio info
    "get_return_series",      # Historical return data
]
```

### 5.2 Benchmark Agent

```python
BENCHMARK_AGENT_PROMPT = """You are the PortfolioIQ Benchmark Analysis Agent. You compare
portfolio performance against market indices.

Your capabilities:
- Compare against Nifty50, Sensex, S&P500, Nasdaq100
- Calculate active return, tracking error, alpha, information ratio
- Compute upside/downside capture ratios
- Rolling performance comparisons
- Period return comparisons (1M, 3M, 6M, 1Y, YTD)

IMPORTANT RULES:
1. Always state which benchmark is being used
2. Present both absolute and relative metrics
3. Explain capture ratios (e.g., "Upside capture of 112% means you captured 112%
   of the benchmark's gains during up periods")
4. Compare appropriate benchmarks (Indian stocks vs Nifty, US stocks vs S&P500)
5. NEVER recommend specific securities
6. Include disclaimer about informational-only analysis
"""

BENCHMARK_AGENT_TOOLS = [
    "get_benchmark_comparison",
    "get_capture_ratios",
    "get_benchmark_list",
    "get_period_returns",
    "get_portfolio_summary",
]
```

### 5.3 Health Agent

```python
HEALTH_AGENT_PROMPT = """You are the PortfolioIQ Health Assessment Agent. You evaluate
overall portfolio wellness using a composite scoring system.

Your capabilities:
- Generate overall health score (0-100) with letter grades
- Break down into 4 subscores: Diversification (25%), Risk (30%),
  Performance (25%), Efficiency (20%)
- Provide specific, actionable recommendations
- Explain each subscore's components in plain English

GRADING SCALE:
- 80-100: Excellent — Portfolio is well-constructed and performing efficiently
- 60-79: Good — Minor improvements possible
- 40-59: Fair — Significant room for improvement
- 20-39: Poor — Material issues need addressing
- 0-19: Critical — Immediate attention required

RECOMMENDATION PRIORITIES:
- High: Actions that significantly impact portfolio health
- Medium: Improvements that would help but aren't urgent
- Low: Nice-to-have optimizations

IMPORTANT RULES:
1. Present the overall score prominently first
2. Break down each subscore with explanation
3. Provide at least 2 actionable recommendations
4. NEVER suggest specific stocks — suggest categories or strategies
5. Include disclaimer
"""

HEALTH_AGENT_TOOLS = [
    "get_health_score",
    "get_subscores",
    "get_portfolio_summary",
    "get_risk_metrics",
    "get_benchmark_comparison",
]
```

### 5.4 Optimization Agent

```python
OPTIMIZATION_AGENT_PROMPT = """You are the PortfolioIQ Optimization Agent. You generate
optimal portfolio allocations using quantitative methods.

Your capabilities:
- Mean-Variance Optimization (Markowitz)
- Maximum Sharpe Ratio portfolio
- Minimum Variance portfolio
- Risk Parity (Equal Risk Contribution)
- Black-Litterman with user views

IMPORTANT RULES:
1. Explain the optimization method being used and its assumptions
2. Present current vs optimal allocations clearly
3. Show expected improvement in return and risk
4. List specific trade recommendations (increase/decrease)
5. Highlight constraints that were active
6. NEVER guarantee returns — use "expected" or "historical"
7. Explain that optimization is based on historical data and past
   performance does not guarantee future results
8. Include disclaimer about informational-only analysis
9. When user asks for "best" portfolio, default to Max Sharpe

LIMITATIONS TO COMMUNICATE:
- Based on historical covariance (backward-looking)
- Sensitive to estimation errors in expected returns
- Does not account for transaction costs unless specified
- Assumes returns are normally distributed (which they aren't)
"""

OPTIMIZATION_AGENT_TOOLS = [
    "run_optimization",
    "get_efficient_frontier",
    "get_portfolio_summary",
    "get_risk_metrics",
]
```

### 5.5 Stress Testing Agent

```python
STRESS_TESTING_AGENT_PROMPT = """You are the PortfolioIQ Stress Testing Agent. You simulate
portfolio performance under historical crisis scenarios.

Available Scenarios:
1. 2008 Global Financial Crisis (Sep 2008 – Mar 2009)
   - Trigger: Lehman Brothers collapse, subprime mortgage crisis
   - S&P 500 decline: ~47%

2. COVID-19 Crash (Feb 2020 – Mar 2020)
   - Trigger: Global pandemic, economic lockdowns
   - S&P 500 decline: ~34%, fastest bear market in history

3. High Inflation 2022 (Jan 2022 – Oct 2022)
   - Trigger: Post-pandemic inflation, supply chain disruptions
   - S&P 500 decline: ~25%

4. Interest Rate Shock (Mar 2022 – Jul 2023)
   - Trigger: Fed raising rates from 0.25% to 5.50%
   - Impact varies by sector (growth vs value, bonds vs equities)

IMPORTANT RULES:
1. Explain the historical context of each scenario
2. Show portfolio impact vs benchmark impact
3. Identify worst-performing holdings and sectors
4. Estimate recovery time based on historical patterns
5. DO NOT predict future crises
6. Frame as "if a similar scenario occurred"
7. Include disclaimer
"""

STRESS_TESTING_AGENT_TOOLS = [
    "run_stress_test",
    "get_scenarios",
    "get_portfolio_summary",
    "get_sector_allocation",
]
```

### 5.6 News Agent

```python
NEWS_AGENT_PROMPT = """You are the PortfolioIQ News Intelligence Agent. You monitor and
analyze news relevant to portfolio holdings.

Your capabilities:
- Fetch recent news for portfolio holdings
- Track earnings announcements and surprises
- Categorize news by relevance and type
- Assess potential portfolio impact

IMPORTANT RULES:
1. Prioritize news by portfolio impact
2. Group news by holding
3. Distinguish between confirmed facts and market speculation
4. Provide context on how news might affect holdings
5. NEVER make predictions about stock price movements
6. Include source attribution for all news items
7. Include disclaimer
"""

NEWS_AGENT_TOOLS = [
    "get_portfolio_news",
    "get_ticker_news",
    "get_earnings_calendar",
    "get_portfolio_summary",
]
```

### 5.7–5.12 Remaining Agents

```python
# Diversification Agent
DIVERSIFICATION_AGENT_TOOLS = [
    "get_concentration_metrics",    # HHI, top-N weight
    "get_correlation_matrix",       # Pairwise correlations
    "get_sector_allocation",        # Sector weights
    "get_portfolio_summary",
]

# Sentiment Agent
SENTIMENT_AGENT_TOOLS = [
    "get_sentiment",                # Per-ticker sentiment
    "get_sentiment_trend",          # Sentiment over time
    "get_portfolio_news",
]

# Performance Attribution Agent
PERFORMANCE_AGENT_TOOLS = [
    "get_performance_attribution",  # Brinson-style attribution
    "get_period_returns",           # Multi-period returns
    "get_sector_returns",           # Sector contribution
    "get_portfolio_summary",
]

# Goal Planning Agent
GOAL_PLANNING_AGENT_TOOLS = [
    "run_goal_simulation",          # Monte Carlo simulation
    "get_projections",              # Wealth projection
    "get_risk_metrics",
    "get_portfolio_summary",
]

# Reporting Agent
REPORTING_AGENT_TOOLS = [
    "generate_report",              # Trigger PDF generation
    "get_report_status",            # Check if report is ready
    "get_portfolio_summary",
]
```

---

## 6. Tool Definitions

### 6.1 Tool Implementation Pattern

Each tool is a callable function that wraps a service layer method:

```python
from langchain_core.tools import tool
from app.services.risk_engine import RiskEngine

@tool
def get_risk_metrics(
    portfolio_id: str,
    lookback_days: int = 252,
    risk_free_rate: float = 0.05,
    benchmark: str = "SP500"
) -> dict:
    """Calculate comprehensive risk metrics for a portfolio.

    Args:
        portfolio_id: UUID of the portfolio
        lookback_days: Number of trading days to look back (default: 252 = 1 year)
        risk_free_rate: Annual risk-free rate (default: 0.05 = 5%)
        benchmark: Benchmark index for relative metrics

    Returns:
        Dictionary containing all risk metrics including Sharpe, Sortino,
        Beta, Alpha, VaR, CVaR, Max Drawdown, and more.
    """
    engine = RiskEngine()
    return engine.calculate_all_metrics(
        portfolio_id=portfolio_id,
        lookback_days=lookback_days,
        risk_free_rate=risk_free_rate,
        benchmark=benchmark
    )
```

### 6.2 Complete Tool Catalog

| Tool Name | Service Layer | Input | Output |
|---|---|---|---|
| `get_portfolio_summary` | `PortfolioService` | `portfolio_id` | Holdings, values, weights |
| `get_sector_allocation` | `PortfolioService` | `portfolio_id` | Sector weight breakdown |
| `get_risk_metrics` | `RiskEngine` | `portfolio_id, lookback, rfr, benchmark` | All risk metrics |
| `get_var_analysis` | `RiskEngine` | `portfolio_id, method, confidence, horizon` | VaR/CVaR details |
| `get_risk_contributions` | `RiskEngine` | `portfolio_id` | Per-holding risk contrib. |
| `get_return_series` | `MarketDataService` | `portfolio_id, period` | Historical returns |
| `get_benchmark_comparison` | `BenchmarkEngine` | `portfolio_id, benchmark, lookback` | Relative metrics |
| `get_capture_ratios` | `BenchmarkEngine` | `portfolio_id, benchmark` | Up/down capture |
| `get_benchmark_list` | `BenchmarkEngine` | None | Available benchmarks |
| `get_period_returns` | `BenchmarkEngine` | `portfolio_id` | Multi-period returns |
| `get_health_score` | `HealthScoreEngine` | `portfolio_id` | Overall + subscores |
| `get_subscores` | `HealthScoreEngine` | `portfolio_id` | Detailed subscore breakdown |
| `run_optimization` | `OptimizationEngine` | `portfolio_id, method, constraints` | Optimal weights |
| `get_efficient_frontier` | `OptimizationEngine` | `portfolio_id` | Frontier data points |
| `run_stress_test` | `StressTestEngine` | `portfolio_id, scenarios` | Scenario impact |
| `get_scenarios` | `StressTestEngine` | None | Available scenarios |
| `get_portfolio_news` | `NewsService` | `portfolio_id, days` | Relevant news articles |
| `get_ticker_news` | `NewsService` | `ticker, days` | Ticker-specific news |
| `get_earnings_calendar` | `NewsService` | `portfolio_id` | Upcoming earnings |
| `get_concentration_metrics` | `PortfolioService` | `portfolio_id` | HHI, top-N metrics |
| `get_correlation_matrix` | `RiskEngine` | `portfolio_id` | Pairwise correlations |
| `get_sentiment` | `NewsService` | `ticker, days` | Sentiment score |
| `get_sentiment_trend` | `NewsService` | `ticker, days` | Sentiment over time |
| `get_performance_attribution` | `PerformanceService` | `portfolio_id, period` | Brinson attribution |
| `get_sector_returns` | `MarketDataService` | `portfolio_id, period` | Per-sector returns |
| `run_goal_simulation` | `GoalPlanningService` | `portfolio_id, goal_params` | Monte Carlo results |
| `get_projections` | `GoalPlanningService` | `portfolio_id, years` | Wealth projection |
| `generate_report` | `ReportingEngine` | `portfolio_id, report_type` | Report ID + status |
| `get_report_status` | `ReportingEngine` | `report_id` | Status + download URL |

---

## 7. Gemini API Integration

### 7.1 Model Configuration

```python
from google import genai

# Model selection
GEMINI_MODEL = "gemini-2.0-flash"          # Primary (fast, cheap)
GEMINI_MODEL_ADVANCED = "gemini-2.5-pro"   # Complex reasoning (fallback)

# Client initialization
client = genai.Client(api_key=settings.GEMINI_API_KEY)

# Generation config
GENERATION_CONFIG = {
    "temperature": 0.3,          # Low temperature for factual accuracy
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 4096,
}

# Router generation config (needs structured output)
ROUTER_GENERATION_CONFIG = {
    "temperature": 0.1,          # Very low for consistent routing
    "top_p": 0.9,
    "max_output_tokens": 512,
    "response_mime_type": "application/json",
}
```

### 7.2 Token Budget Management

```python
TOKEN_BUDGETS = {
    "router":          512,       # Intent classification (small)
    "agent_context":   2048,      # Tool results passed to agent
    "agent_response":  4096,      # Agent analysis response
    "synthesizer":     4096,      # Final synthesized response
    "total_per_query": 12000,     # Max tokens per user query
}
```

### 7.3 Context Window Strategy

```
User query arrives
    │
    ├── System prompt (~500 tokens)
    ├── Conversation history (last 5 messages, ~2000 tokens max)
    ├── Portfolio context (summary, ~500 tokens)
    ├── Tool results (~2000 tokens)
    └── Generation budget (~4000 tokens)
    ────────────────────────────
    Total: ~9000 tokens per agent call
```

---

## 8. Memory Architecture

### 8.1 Conversation Memory (PostgreSQL)

Short-term memory stored in `copilot_sessions` and `copilot_messages` tables.

```python
class ConversationMemory:
    """Manages conversation history in PostgreSQL."""

    async def get_recent_messages(
        self,
        session_id: str,
        limit: int = 10
    ) -> list[BaseMessage]:
        """Retrieve last N messages for context window."""
        ...

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent_name: str = None,
        citations: list = None
    ) -> None:
        """Persist a message to the conversation."""
        ...

    async def get_session_summary(
        self,
        session_id: str
    ) -> str:
        """Generate a summary of the conversation so far."""
        # Uses Gemini to summarize if conversation exceeds context window
        ...
```

### 8.2 Semantic Memory (Qdrant)

Long-term vector-based memory for RAG and personalization.

```python
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

# Collections
QDRANT_COLLECTIONS = {
    "news_embeddings": {
        "size": 768,                    # Gemini embedding dimension
        "distance": Distance.COSINE,
        "purpose": "News article retrieval"
    },
    "conversation_embeddings": {
        "size": 768,
        "distance": Distance.COSINE,
        "purpose": "Past conversation retrieval"
    },
    "financial_knowledge": {
        "size": 768,
        "distance": Distance.COSINE,
        "purpose": "Financial concepts and definitions"
    }
}

class SemanticMemory:
    def __init__(self):
        self.client = QdrantClient(host="localhost", port=6333)

    async def search_similar(
        self,
        collection: str,
        query_text: str,
        limit: int = 5,
        filters: dict = None
    ) -> list[dict]:
        """Search for semantically similar content."""
        # 1. Embed query using Gemini
        # 2. Search Qdrant collection
        # 3. Return ranked results with metadata
        ...

    async def upsert_embedding(
        self,
        collection: str,
        text: str,
        metadata: dict,
        id: str
    ) -> None:
        """Store a new embedding."""
        ...
```

### 8.3 Memory Flow

```
User sends message
       │
       ▼
┌─────────────────────┐
│ 1. Retrieve recent   │──── PostgreSQL: last 5 messages
│    conversation       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 2. Retrieve relevant │──── Qdrant: semantic search on query
│    past context       │     (previous sessions, news)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 3. Build context     │──── Combine: system prompt + memory + query
│    window            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 4. Process & respond │──── LangGraph execution
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 5. Store response    │──── PostgreSQL: save message
│    & embed           │──── Qdrant: embed for future retrieval
└─────────────────────┘
```

---

## 9. RAG Pipeline

### 9.1 News RAG

```
News articles fetched (Finnhub / NewsAPI)
       │
       ▼
┌─────────────────────┐
│ 1. Extract text      │──── Title + summary + content
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 2. Chunk (if long)   │──── Max 1000 chars per chunk
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 3. Embed via Gemini  │──── models/text-embedding-004
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 4. Store in Qdrant   │──── Collection: news_embeddings
│                      │──── Metadata: ticker, date, source
└─────────────────────┘

At query time:
User asks "any news about AAPL?"
       │
       ▼
┌─────────────────────┐
│ 1. Embed query       │
│ 2. Search Qdrant     │──── Filter: ticker=AAPL, date>7d ago
│ 3. Retrieve top 5    │
│ 4. Pass to agent     │──── Agent analyzes and summarizes
└─────────────────────┘
```

### 9.2 Embedding Model

```python
# Using Gemini's embedding model
EMBEDDING_MODEL = "models/text-embedding-004"
EMBEDDING_DIMENSION = 768

async def embed_text(text: str) -> list[float]:
    """Generate embedding vector for text."""
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
    )
    return result.embeddings[0].values
```

---

## 10. Guardrails System

### 10.1 Guardrail Rules

```python
GUARDRAIL_RULES = {
    "no_financial_advice": {
        "description": "Never provide direct financial advice",
        "check": "output must not contain buy/sell recommendations for specific securities",
        "action": "append_disclaimer"
    },
    "citation_required": {
        "description": "All numerical claims must have citations",
        "check": "every metric mentioned must link to a tool call result",
        "action": "flag_uncited_claims"
    },
    "no_guarantees": {
        "description": "Never guarantee returns or outcomes",
        "check": "output must not contain 'will', 'guaranteed', 'certain'",
        "action": "soften_language"
    },
    "disclaimer_present": {
        "description": "Every response must include a disclaimer",
        "check": "response ends with standard disclaimer",
        "action": "append_disclaimer"
    }
}

STANDARD_DISCLAIMER = (
    "\n\n---\n*This analysis is informational only and does not constitute financial advice. "
    "Past performance does not guarantee future results. Consult a qualified financial "
    "advisor before making investment decisions.*"
)
```

### 10.2 Guardrail Node Implementation

```python
async def guardrails_node(state: CopilotState) -> CopilotState:
    """Apply guardrails to the synthesized response."""
    response = state["final_response"]
    flags = []

    # Check for financial advice language
    advice_patterns = [
        r"\byou should buy\b",
        r"\byou should sell\b",
        r"\bI recommend buying\b",
        r"\bI recommend selling\b",
        r"\bbuy .+ stock\b",
        r"\bsell .+ stock\b",
    ]
    for pattern in advice_patterns:
        if re.search(pattern, response, re.IGNORECASE):
            flags.append("financial_advice_detected")
            response = re.sub(
                pattern,
                "[Analysis suggests considering]",
                response,
                flags=re.IGNORECASE
            )

    # Check for guarantee language
    guarantee_patterns = [
        r"\bwill definitely\b",
        r"\bguaranteed\b",
        r"\bcertain to\b",
        r"\bwill increase\b",
        r"\bwill decrease\b",
    ]
    for pattern in guarantee_patterns:
        if re.search(pattern, response, re.IGNORECASE):
            flags.append("guarantee_language_detected")
            response = response.replace(
                re.search(pattern, response, re.IGNORECASE).group(),
                "may potentially"
            )

    # Ensure disclaimer is present
    if STANDARD_DISCLAIMER not in response:
        response += STANDARD_DISCLAIMER

    return {
        **state,
        "final_response": response,
        "guardrail_flags": flags,
    }
```

---

## 11. Response Synthesizer

### 11.1 Multi-Agent Response Merging

```python
SYNTHESIZER_PROMPT = """You are the PortfolioIQ Response Synthesizer. You receive analysis
results from one or more specialized agents and must create a unified, coherent response.

RULES:
1. Merge overlapping information (don't repeat the same metric from two agents)
2. Present information in a logical order:
   - Lead with the most relevant answer to the user's question
   - Follow with supporting data
   - End with recommendations (if any)
3. Maintain all citations from individual agents
4. Use clear formatting (headers, bullet points, tables where appropriate)
5. Keep the tone professional but accessible
6. If agents disagree, present both perspectives
7. Do NOT add information that wasn't provided by the agents

Agent results to synthesize:
{agent_results}

Original user question:
{user_query}
"""
```

### 11.2 Citation Format

```python
class Citation(TypedDict):
    source: str          # Tool/service that produced the data
    data_point: str      # What was measured
    value: Any           # The actual value
    timestamp: str       # When it was calculated

# Example citations in response
"""
Your portfolio's Sharpe ratio is **1.26** [¹], which is considered "very good"
by institutional standards. Your annualized return of **28.34%** [²] significantly
outperforms the S&P 500's **23.11%** [³].

---
Citations:
[¹] Risk Engine: Sharpe Ratio = 1.2567 (252-day lookback)
[²] Risk Engine: Annualized Return = 28.34% (252-day lookback)
[³] Benchmark Engine: S&P 500 1Y Return = 23.11%
"""
```

---

## 12. Error Handling & Fallbacks

### 12.1 Agent Error Handling

```python
async def safe_agent_execution(
    agent_func: callable,
    state: CopilotState,
    timeout: int = 30
) -> CopilotState:
    """Execute an agent with error handling and timeout."""
    try:
        result = await asyncio.wait_for(
            agent_func(state),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        return {
            **state,
            "agent_results": state["agent_results"] + [{
                "agent_name": state["current_agent"],
                "content": "Analysis timed out. Please try again.",
                "citations": [],
                "tool_calls": [],
                "confidence": 0.0,
                "error": "timeout"
            }]
        }
    except Exception as e:
        return {
            **state,
            "agent_results": state["agent_results"] + [{
                "agent_name": state["current_agent"],
                "content": f"Analysis encountered an error: {str(e)}",
                "citations": [],
                "tool_calls": [],
                "confidence": 0.0,
                "error": str(e)
            }]
        }
```

### 12.2 Fallback Strategy

```
Agent fails
    │
    ├── Timeout (30s) → Return partial results + apology
    ├── Tool error → Return cached results if available
    ├── LLM error → Retry once with simpler prompt
    ├── Data error → Return "insufficient data" message
    └── All retries fail → Return graceful error message
```

### 12.3 Rate Limit Management

```python
GEMINI_RATE_LIMITS = {
    "requests_per_minute": 15,     # Free tier limit
    "tokens_per_minute": 1000000,
    "requests_per_day": 1500,
}

# Implement token bucket rate limiter
class GeminiRateLimiter:
    def __init__(self):
        self.request_bucket = TokenBucket(
            capacity=15,
            fill_rate=15/60  # 15 per minute
        )

    async def acquire(self):
        """Wait until a request slot is available."""
        while not self.request_bucket.consume(1):
            await asyncio.sleep(0.5)
```

---

## 13. Streaming Architecture

### 13.1 SSE (Server-Sent Events) Flow

```python
from fastapi.responses import StreamingResponse

@router.post("/copilot/sessions/{session_id}/messages/stream")
async def stream_copilot_response(
    session_id: UUID,
    request: CopilotMessageRequest,
    current_user: User = Depends(get_current_user),
):
    async def event_stream():
        async for event in copilot.process_stream(
            session_id=session_id,
            user_message=request.content,
            user_id=current_user.id,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

### 13.2 Event Types

```typescript
// Frontend TypeScript types for SSE events
type CopilotEvent =
    | { type: "thinking"; agent: string; content: string }
    | { type: "tool_call"; agent: string; tool: string; args: Record<string, any> }
    | { type: "tool_result"; agent: string; tool: string; result: Record<string, any> }
    | { type: "token"; content: string }
    | { type: "citation"; source: string; data_point: string; value: any }
    | { type: "error"; message: string }
    | { type: "done"; message_id: string };
```

---

## 14. Agent Testing Strategy

### 14.1 Unit Tests

```python
# Test each agent independently with mocked tools
class TestRiskAgent:
    async def test_sharpe_ratio_query(self):
        """Risk agent correctly invokes get_risk_metrics and formats response."""
        state = create_test_state(
            query="What is my Sharpe ratio?",
            portfolio_id="test-uuid"
        )
        result = await risk_agent_node(state)
        assert "sharpe" in result["agent_results"][-1]["content"].lower()
        assert len(result["agent_results"][-1]["citations"]) > 0

    async def test_var_query(self):
        """Risk agent handles VaR queries with confidence level."""
        ...

    async def test_no_financial_advice(self):
        """Risk agent never gives buy/sell recommendations."""
        ...
```

### 14.2 Integration Tests

```python
# Test full graph execution with real services
class TestCopilotIntegration:
    async def test_single_agent_query(self):
        """Simple query routes to one agent and produces response."""
        ...

    async def test_multi_agent_query(self):
        """Complex query routes to multiple agents and merges results."""
        ...

    async def test_guardrails_applied(self):
        """Response includes disclaimer and no financial advice."""
        ...

    async def test_streaming(self):
        """SSE stream produces valid events in correct order."""
        ...
```

### 14.3 Evaluation Metrics

| Metric              | Target  | How to Measure                              |
|---------------------|---------|---------------------------------------------|
| Routing accuracy    | > 90%   | Correct agent selection for 50 test queries |
| Citation accuracy   | > 95%   | All cited numbers match tool results        |
| Response latency    | < 5s    | Time from query to first token              |
| Guardrail pass rate | 100%    | No uncaught financial advice                |
| Tool call accuracy  | > 95%   | Correct tools invoked with valid params     |

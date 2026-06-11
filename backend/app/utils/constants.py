"""Shared constants for PortfolioIQ."""

import enum


class CurrencyCode(str, enum.Enum):
    USD = "USD"
    INR = "INR"
    EUR = "EUR"
    GBP = "GBP"


class PortfolioStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"


class TransactionType(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    SPLIT = "split"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class InstrumentType(str, enum.Enum):
    EQUITY = "equity"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    BOND = "bond"
    INDEX = "index"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    CASH = "cash"


class ExchangeCode(str, enum.Enum):
    NSE = "NSE"
    BSE = "BSE"
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    AMEX = "AMEX"
    LSE = "LSE"
    OTHER = "OTHER"


class BenchmarkType(str, enum.Enum):
    NIFTY50 = "NIFTY50"
    SENSEX = "SENSEX"
    SP500 = "SP500"
    NASDAQ100 = "NASDAQ100"


class HealthGrade(str, enum.Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


# Benchmark ticker mapping (yfinance symbols)
BENCHMARK_TICKERS = {
    BenchmarkType.NIFTY50: "^NSEI",
    BenchmarkType.SENSEX: "^BSESN",
    BenchmarkType.SP500: "^GSPC",
    BenchmarkType.NASDAQ100: "^NDX",
}

# CSV upload settings
REQUIRED_CSV_COLUMNS = {"ticker", "quantity", "average_cost"}
OPTIONAL_CSV_COLUMNS = {"currency", "name", "sector"}

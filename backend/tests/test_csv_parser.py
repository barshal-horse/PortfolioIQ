"""Tests for CSV parser."""

import pytest

from app.utils.csv_parser import parse_holdings_csv


class TestCSVParser:
    """Tests for parse_holdings_csv function."""

    def test_valid_csv_basic(self):
        """Parse a simple valid CSV with required columns."""
        csv_content = """ticker,quantity,average_cost
AAPL,50,150.00
MSFT,30,280.00
GOOGL,20,140.00"""

        result = parse_holdings_csv(csv_content)

        assert len(result.holdings) == 3
        assert result.skipped == 0
        assert len(result.errors) == 0

        assert result.holdings[0].ticker == "AAPL"
        assert result.holdings[0].quantity == 50.0
        assert result.holdings[0].average_cost == 150.0
        assert result.holdings[0].currency == "USD"  # Default

    def test_valid_csv_with_currency(self):
        """Parse CSV with optional currency column."""
        csv_content = """ticker,quantity,average_cost,currency
RELIANCE.NS,100,2500.00,INR
TCS.NS,50,3500.00,INR
AAPL,25,190.00,USD"""

        result = parse_holdings_csv(csv_content)

        assert len(result.holdings) == 3
        assert result.holdings[0].ticker == "RELIANCE.NS"
        assert result.holdings[0].currency == "INR"
        assert result.holdings[2].currency == "USD"

    def test_missing_required_columns(self):
        """Error when required columns are missing."""
        csv_content = """ticker,quantity
AAPL,50"""

        result = parse_holdings_csv(csv_content)

        assert len(result.holdings) == 0
        assert len(result.errors) == 1
        assert "Missing required columns" in result.errors[0].error
        assert "average_cost" in result.errors[0].error

    def test_empty_csv(self):
        """Error on empty CSV."""
        result = parse_holdings_csv("")

        assert len(result.holdings) == 0
        assert len(result.errors) == 1

    def test_invalid_quantity(self):
        """Skip rows with invalid quantity values."""
        csv_content = """ticker,quantity,average_cost
AAPL,fifty,150.00
MSFT,-10,280.00
GOOGL,20,140.00"""

        result = parse_holdings_csv(csv_content)

        assert len(result.holdings) == 1  # Only GOOGL
        assert result.skipped == 2
        assert result.holdings[0].ticker == "GOOGL"

    def test_invalid_cost(self):
        """Skip rows with invalid average_cost values."""
        csv_content = """ticker,quantity,average_cost
AAPL,50,free
MSFT,30,0
GOOGL,20,140.00"""

        result = parse_holdings_csv(csv_content)

        assert len(result.holdings) == 1
        assert result.skipped == 2

    def test_empty_ticker(self):
        """Skip rows with missing ticker."""
        csv_content = """ticker,quantity,average_cost
,50,150.00
MSFT,30,280.00"""

        result = parse_holdings_csv(csv_content)

        assert len(result.holdings) == 1
        assert result.skipped == 1
        assert result.holdings[0].ticker == "MSFT"

    def test_ticker_normalization(self):
        """Tickers should be uppercased."""
        csv_content = """ticker,quantity,average_cost
aapl,50,150.00
msft,30,280.00"""

        result = parse_holdings_csv(csv_content)

        assert result.holdings[0].ticker == "AAPL"
        assert result.holdings[1].ticker == "MSFT"

    def test_whitespace_handling(self):
        """Handle whitespace in values."""
        csv_content = """ticker, quantity, average_cost
  AAPL  , 50 , 150.00 """

        result = parse_holdings_csv(csv_content)

        assert len(result.holdings) == 1
        assert result.holdings[0].ticker == "AAPL"

    def test_bytes_input(self):
        """Accept bytes input (from file upload)."""
        csv_content = b"ticker,quantity,average_cost\nAAPL,50,150.00"

        result = parse_holdings_csv(csv_content)

        assert len(result.holdings) == 1

    def test_bom_handling(self):
        """Handle UTF-8 BOM from Excel exports."""
        csv_content = b"\xef\xbb\xbfticker,quantity,average_cost\nAAPL,50,150.00"

        result = parse_holdings_csv(csv_content)

        assert len(result.holdings) == 1
        assert result.holdings[0].ticker == "AAPL"

    def test_partial_import(self):
        """Mix of valid and invalid rows — valid rows imported, errors reported."""
        csv_content = """ticker,quantity,average_cost
AAPL,50,150.00
INVALID!!,30,280.00
GOOGL,20,140.00
MSFT,-5,100.00"""

        result = parse_holdings_csv(csv_content)

        assert len(result.holdings) == 2  # AAPL, GOOGL
        assert result.skipped == 2
        assert len(result.errors) == 2

    def test_fractional_shares(self):
        """Support fractional share quantities."""
        csv_content = """ticker,quantity,average_cost
AAPL,0.5,150.00
BRK-B,1.25,380.00"""

        result = parse_holdings_csv(csv_content)

        assert len(result.holdings) == 2
        assert result.holdings[0].quantity == 0.5
        assert result.holdings[1].quantity == 1.25

    def test_indian_tickers(self):
        """Support NSE/BSE ticker formats (e.g., RELIANCE.NS)."""
        csv_content = """ticker,quantity,average_cost,currency
RELIANCE.NS,100,2500.00,INR
INFY.NS,200,1500.00,INR
^NSEI,10,22000.00,INR"""

        result = parse_holdings_csv(csv_content)

        assert len(result.holdings) == 3
        assert result.holdings[0].ticker == "RELIANCE.NS"
        assert result.holdings[2].ticker == "^NSEI"

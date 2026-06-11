"""CSV parser for portfolio holdings upload.

Handles:
- Column detection (required: ticker, quantity, average_cost)
- Per-row validation with error collection
- Ticker normalization (uppercase, whitespace stripped)
- Graceful partial imports (valid rows imported, errors reported)
"""

import csv
import io
from dataclasses import dataclass, field

from app.schemas.holding import BulkHoldingItem, CSVUploadError
from app.utils.constants import REQUIRED_CSV_COLUMNS, OPTIONAL_CSV_COLUMNS


@dataclass
class CSVParseResult:
    """Result of parsing a CSV file."""

    holdings: list[BulkHoldingItem] = field(default_factory=list)
    errors: list[CSVUploadError] = field(default_factory=list)
    skipped: int = 0


def parse_holdings_csv(file_content: str | bytes) -> CSVParseResult:
    """Parse a CSV string/bytes into a list of BulkHoldingItems.

    Expected CSV format:
        ticker,quantity,average_cost[,currency]
        AAPL,50,150.00,USD
        RELIANCE.NS,100,2500.00,INR

    Returns:
        CSVParseResult with valid holdings, errors, and skip count.
    """
    result = CSVParseResult()

    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8-sig")  # Handle BOM

    reader = csv.DictReader(io.StringIO(file_content))

    if reader.fieldnames is None:
        result.errors.append(
            CSVUploadError(row=0, error="CSV file is empty or has no header row")
        )
        return result

    # Normalize header names (lowercase, strip whitespace)
    normalized_headers = {h.strip().lower().replace(" ", "_") for h in reader.fieldnames}

    # Validate required columns
    missing = REQUIRED_CSV_COLUMNS - normalized_headers
    if missing:
        result.errors.append(
            CSVUploadError(
                row=0,
                error=f"Missing required columns: {', '.join(sorted(missing))}. "
                f"Required: {', '.join(sorted(REQUIRED_CSV_COLUMNS))}",
            )
        )
        return result

    # Build header mapping (original → normalized)
    header_map: dict[str, str] = {}
    for original in reader.fieldnames:
        normalized = original.strip().lower().replace(" ", "_")
        header_map[original] = normalized

    for row_num, row in enumerate(reader, start=2):  # Row 1 is header
        try:
            # Map to normalized keys
            normalized_row = {header_map[k]: v.strip() for k, v in row.items() if v}

            ticker = normalized_row.get("ticker", "").strip().upper()
            if not ticker:
                result.errors.append(
                    CSVUploadError(row=row_num, error="Missing ticker")
                )
                result.skipped += 1
                continue

            # Validate ticker format
            if not _is_valid_ticker(ticker):
                result.errors.append(
                    CSVUploadError(
                        row=row_num,
                        ticker=ticker,
                        error=f"Invalid ticker format: '{ticker}'",
                    )
                )
                result.skipped += 1
                continue

            # Parse quantity
            qty_str = normalized_row.get("quantity", "")
            try:
                quantity = float(qty_str)
                if quantity <= 0:
                    raise ValueError("must be positive")
            except (ValueError, TypeError):
                result.errors.append(
                    CSVUploadError(
                        row=row_num,
                        ticker=ticker,
                        error=f"Invalid quantity: '{qty_str}' (must be a positive number)",
                    )
                )
                result.skipped += 1
                continue

            # Parse average cost
            cost_str = normalized_row.get("average_cost", "")
            try:
                average_cost = float(cost_str)
                if average_cost <= 0:
                    raise ValueError("must be positive")
            except (ValueError, TypeError):
                result.errors.append(
                    CSVUploadError(
                        row=row_num,
                        ticker=ticker,
                        error=f"Invalid average_cost: '{cost_str}' (must be a positive number)",
                    )
                )
                result.skipped += 1
                continue

            # Parse optional currency
            currency = normalized_row.get("currency", "USD").upper()
            if currency not in {"USD", "INR", "EUR", "GBP"}:
                currency = "USD"  # Default to USD if unrecognized

            result.holdings.append(
                BulkHoldingItem(
                    ticker=ticker,
                    quantity=quantity,
                    average_cost=average_cost,
                    currency=currency,
                )
            )

        except Exception as e:
            result.errors.append(
                CSVUploadError(
                    row=row_num,
                    error=f"Unexpected error parsing row: {str(e)}",
                )
            )
            result.skipped += 1

    return result


def _is_valid_ticker(ticker: str) -> bool:
    """Validate ticker format: alphanumeric with dots, hyphens, carets allowed."""
    if not ticker or len(ticker) > 20:
        return False
    import re

    return bool(re.match(r"^[A-Z0-9.\-^]+$", ticker))

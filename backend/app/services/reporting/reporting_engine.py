"""Reporting Engine — PDF generation for portfolio reports."""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image,
    KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.report import Report
from app.models.portfolio import Portfolio
from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.user import User
from app.utils.ids import to_uuid as _to_uuid


# Report output directory
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

# Color palette
BRAND_CYAN = colors.HexColor("#06B6D4")
BRAND_VIOLET = colors.HexColor("#8B5CF6")
BRAND_GREEN = colors.HexColor("#10B981")
BRAND_RED = colors.HexColor("#EF4444")
DARK_BG = colors.HexColor("#0A101D")
CARD_BG = colors.HexColor("#131B2E")
BORDER_COLOR = colors.HexColor("#1E293B")
TEXT_PRIMARY = colors.HexColor("#F1F5F9")
TEXT_SECONDARY = colors.HexColor("#94A3B8")


def generate_chart_image(chart_func, width=6, height=3):
    """Generate a chart as PNG bytes."""
    fig, ax = plt.subplots(figsize=(width, height), facecolor='#0A101D')
    ax.set_facecolor('#0A101D')
    chart_func(ax)
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor='#0A101D', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def draw_valuation_chart(ax, portfolio_data: Dict):
    """Draw portfolio valuation growth chart."""
    dates = portfolio_data.get("valuation_dates", [])
    values = portfolio_data.get("valuation_values", [])
    
    if not dates or not values:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', color='white')
        return
    
    ax.plot(dates, values, color='#06B6D4', linewidth=2)
    ax.fill_between(dates, values, alpha=0.1, color='#06B6D4')
    ax.set_title('Portfolio Valuation', color='white', fontsize=12, pad=10)
    ax.tick_params(colors='#94A3B8', labelsize=8)
    for spine in ax.spines.values():
        spine.set_color('#1E293B')


def draw_sector_pie(ax, sector_data: Dict):
    """Draw sector allocation pie chart."""
    labels = list(sector_data.keys())
    values = list(sector_data.values())
    
    if not labels or not values:
        ax.text(0.5, 0.5, 'No sector data', ha='center', va='center', color='white')
        return
    
    colors_list = ['#06B6D4', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#3B82F6', '#84CC16']
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct='%1.1f%%',
        colors=colors_list[:len(labels)], startangle=90,
        textprops={'color': 'white', 'fontsize': 8}
    )
    ax.set_title('Sector Allocation', color='white', fontsize=12, pad=10)


def draw_efficient_frontier(ax, frontier_data: Dict):
    """Draw efficient frontier chart."""
    returns = frontier_data.get("returns", [])
    volatilities = frontier_data.get("volatilities", [])
    current = frontier_data.get("current_position")
    optimal = frontier_data.get("optimal_position")
    
    if not returns or not volatilities:
        ax.text(0.5, 0.5, 'No frontier data', ha='center', va='center', color='white')
        return
    
    ax.scatter(volatilities, returns, c='#8B5CF6', alpha=0.6, s=20, label='Frontier')
    if current:
        ax.scatter([current[1]], [current[0]], c='#EF4444', s=100, marker='*', label='Current', zorder=5)
    if optimal:
        ax.scatter([optimal[1]], [optimal[0]], c='#10B981', s=100, marker='*', label='Optimal', zorder=5)
    
    ax.set_xlabel('Volatility (%)', color='#94A3B8', fontsize=8)
    ax.set_ylabel('Return (%)', color='#94A3B8', fontsize=8)
    ax.set_title('Efficient Frontier', color='white', fontsize=12, pad=10)
    ax.legend(fontsize=7, facecolor='#131B2E', edgecolor='#1E293B')
    ax.tick_params(colors='#94A3B8', labelsize=8)
    for spine in ax.spines.values():
        spine.set_color('#1E293B')


class ReportingEngine:
    """Engine for generating portfolio PDF reports."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Create custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=TEXT_PRIMARY,
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=14,
            textColor=BRAND_CYAN,
            spaceBefore=18,
            spaceAfter=8,
            fontName='Helvetica-Bold',
        ))
        self.styles.add(ParagraphStyle(
            name='SubHeader',
            parent=self.styles['Heading2'],
            fontSize=11,
            textColor=TEXT_SECONDARY,
            spaceBefore=12,
            spaceAfter=4,
            fontName='Helvetica',
        ))
        self.styles.add(ParagraphStyle(
            name='BodyText2',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=TEXT_PRIMARY,
            spaceAfter=4,
            fontName='Helvetica',
            leading=12,
        ))
        self.styles.add(ParagraphStyle(
            name='MetricLabel',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=TEXT_SECONDARY,
            fontName='Helvetica',
        ))
        self.styles.add(ParagraphStyle(
            name='MetricValue',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=TEXT_PRIMARY,
            fontName='Helvetica-Bold',
        ))
        self.styles.add(ParagraphStyle(
            name='TableHeader',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=TEXT_PRIMARY,
            fontName='Helvetica-Bold',
        ))
        self.styles.add(ParagraphStyle(
            name='TableCell',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=TEXT_PRIMARY,
            fontName='Helvetica',
        ))
        self.styles.add(ParagraphStyle(
            name='Disclaimer',
            parent=self.styles['Normal'],
            fontSize=7,
            textColor=TEXT_SECONDARY,
            fontName='Helvetica-Oblique',
            alignment=TA_CENTER,
        ))

    def _create_header_table(self, portfolio: Portfolio, user: Optional[User]) -> Table:
        """Create report header table."""
        owner_name = getattr(user, "full_name", None) or "Unknown Owner"
        owner_email = getattr(user, "email", None) or "unknown"
        data = [
            [Paragraph("PortfolioIQ", self.styles['ReportTitle']), ""],
            [Paragraph(f"{portfolio.name}", self.styles['SectionHeader']), ""],
            [Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%B %d, %Y %H:%M UTC')}", self.styles['BodyText2']), ""],
            [Paragraph(f"Owner: {owner_name} ({owner_email})", self.styles['BodyText2']), ""],
        ]
        
        table = Table(data, colWidths=[5.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), DARK_BG),
            ('TEXTCOLOR', (0, 0), (-1, -1), TEXT_PRIMARY),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
            ('LINEBELOW', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ]))
        return table

    def _create_metrics_table(self, portfolio_data: Dict) -> Table:
        """Create key metrics summary table."""
        metrics = portfolio_data.get("metrics", {})
        
        data = [
            ["Metric", "Value", "Metric", "Value"],
            [
                "Total Value", f"${metrics.get('total_value', 0):,.2f}",
                "Cost Basis", f"${metrics.get('total_cost', 0):,.2f}"
            ],
            [
                "Unrealized P&L", f"${metrics.get('unrealized_pnl', 0):,.2f}",
                "Total Return", f"{metrics.get('pnl_percentage', 0):.2f}%"
            ],
            [
                "Annualized Return", f"{metrics.get('annualized_return', 0)*100:.2f}%",
                "Volatility", f"{metrics.get('annualized_volatility', 0)*100:.2f}%"
            ],
            [
                "Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}",
                "Max Drawdown", f"{metrics.get('max_drawdown', 0)*100:.2f}%"
            ],
        ]
        
        table = Table(data, colWidths=[1.75*inch, 1.75*inch, 1.75*inch, 1.75*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_CYAN),
            ('TEXTCOLOR', (0, 0), (-1, 0), TEXT_PRIMARY),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BACKGROUND', (0, 1), (-1, -1), CARD_BG),
            ('TEXTCOLOR', (0, 1), (-1, -1), TEXT_PRIMARY),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [CARD_BG, DARK_BG]),
        ]))
        return table

    def _create_holdings_table(self, holdings: List[Dict]) -> Table:
        """Create holdings detail table."""
        if not holdings:
            return Paragraph("No holdings data available.", self.styles['BodyText2'])
        
        data = [["Ticker", "Name", "Qty", "Avg Cost", "Current", "Value", "P&L", "Weight"]]
        
        for h in holdings:
            pnl_color = BRAND_GREEN if h.get('unrealized_pnl', 0) >= 0 else BRAND_RED
            pnl_text = f"${h.get('unrealized_pnl', 0):,.2f}"
            
            data.append([
                h.get('ticker', ''),
                h.get('name', '')[:20],
                f"{h.get('quantity', 0):,.4f}",
                f"${h.get('average_cost', 0):,.2f}",
                f"${h.get('current_price', 0):,.2f}",
                f"${h.get('current_value', 0):,.2f}",
                pnl_text,
                f"{h.get('weight', 0)*100:.2f}%",
            ])
        
        col_widths = [0.7*inch, 1.2*inch, 0.6*inch, 0.8*inch, 0.8*inch, 0.9*inch, 0.9*inch, 0.6*inch]
        
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_CYAN),
            ('TEXTCOLOR', (0, 0), (-1, 0), TEXT_PRIMARY),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), CARD_BG),
            ('TEXTCOLOR', (0, 1), (-1, -1), TEXT_PRIMARY),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [CARD_BG, DARK_BG]),
        ]))
        return table

    def _create_risk_table(self, risk_data: Dict) -> Table:
        """Create risk metrics table."""
        metrics = risk_data.get("metrics", {})
        
        data = [
            ["Risk Metric", "Value", "Risk Metric", "Value"],
            [
                "Volatility (Ann.)", f"{metrics.get('annualized_volatility', 0)*100:.2f}%",
                "Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}"
            ],
            [
                "Sortino Ratio", f"{metrics.get('sortino_ratio', 0):.2f}",
                "Beta", f"{metrics.get('beta', 0):.2f}"
            ],
            [
                "Alpha (Ann.)", f"{metrics.get('alpha', 0)*100:.2f}%",
                "Max Drawdown", f"{metrics.get('max_drawdown', 0)*100:.2f}%"
            ],
            [
                "VaR 95% (Daily)", f"{metrics.get('var_95', 0)*100:.2f}%",
                "CVaR 95% (Daily)", f"{metrics.get('cvar_95', 0)*100:.2f}%"
            ],
        ]
        
        table = Table(data, colWidths=[1.75*inch, 1.75*inch, 1.75*inch, 1.75*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_VIOLET),
            ('TEXTCOLOR', (0, 0), (-1, 0), TEXT_PRIMARY),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BACKGROUND', (0, 1), (-1, -1), CARD_BG),
            ('TEXTCOLOR', (0, 1), (-1, -1), TEXT_PRIMARY),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [CARD_BG, DARK_BG]),
        ]))
        return table

    def _create_health_table(self, health_data: Dict) -> Table:
        """Create health score table."""
        overall = health_data.get("overall", {})
        subscores = health_data.get("subscores", {})
        
        data = [
            ["Component", "Score", "Grade", "Weight"],
            ["Overall", str(overall.get("score", 0)), overall.get("grade", "").title(), "100%"],
            ["Diversification", str(subscores.get("diversification", {}).get("score", 0)),
             subscores.get("diversification", {}).get("grade", "").title(), "25%"],
            ["Risk Control", str(subscores.get("risk", {}).get("score", 0)),
             subscores.get("risk", {}).get("grade", "").title(), "30%"],
            ["Performance", str(subscores.get("performance", {}).get("score", 0)),
             subscores.get("performance", {}).get("grade", "").title(), "25%"],
            ["Efficiency", str(subscores.get("efficiency", {}).get("score", 0)),
             subscores.get("efficiency", {}).get("grade", "").title(), "20%"],
        ]
        
        table = Table(data, colWidths=[2*inch, 1*inch, 1.5*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_GREEN),
            ('TEXTCOLOR', (0, 0), (-1, 0), TEXT_PRIMARY),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BACKGROUND', (0, 1), (-1, -1), CARD_BG),
            ('TEXTCOLOR', (0, 1), (-1, -1), TEXT_PRIMARY),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),
            ('ALIGN', (3, 1), (3, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [CARD_BG, DARK_BG]),
        ]))
        return table

    async def _gather_report_data(
        self,
        db: AsyncSession,
        portfolio_id: uuid.UUID,
        user_id: uuid.UUID,
        report_type: str,
    ) -> Dict[str, Any]:
        """Gather all data needed for report generation."""
        portfolio_id = _to_uuid(portfolio_id)
        user_id = _to_uuid(user_id)

        # Get portfolio with holdings
        result = await db.execute(
            select(Portfolio)
            .where(and_(Portfolio.id == portfolio_id, Portfolio.user_id == user_id))
        )
        portfolio = result.scalar_one_or_none()
        if not portfolio:
            raise ValueError("Portfolio not found")

        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        # Get holdings with instruments
        holdings_result = await db.execute(
            select(Holding, Instrument)
            .join(Instrument, Holding.instrument_id == Instrument.id)
            .where(Holding.portfolio_id == portfolio_id)
        )
        holdings = []
        for h, i in holdings_result.all():
            holdings.append({
                "ticker": h.ticker,
                "name": i.name if i else h.ticker,
                "sector": i.sector if i else "Unknown",
                "quantity": float(h.quantity or 0),
                "average_cost": float(h.average_cost or 0),
                "current_price": float(h.current_price or 0),
                "current_value": float(h.current_value or 0),
                "unrealized_pnl": float(h.unrealized_pnl or 0),
                "weight": float(h.weight or 0),
            })

        # Gather analytics based on report type
        portfolio_data = {
            "portfolio": portfolio,
            "user": user,
            "holdings": holdings,
            "metrics": {
                "total_value": float(portfolio.total_value or 0),
                "total_cost": float(portfolio.total_cost or 0),
                "unrealized_pnl": float(portfolio.unrealized_pnl or 0),
                "pnl_percentage": float(portfolio.pnl_percentage or 0),
                "annualized_return": 0.0,
                "annualized_volatility": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
            },
        }

        # Try to fetch risk metrics if available
        try:
            from app.services import risk_engine
            risk_result = await risk_engine.calculate_portfolio_risk(
                db=db,
                portfolio_id=str(portfolio_id),
                user_id=str(user_id),
                lookback_days=252,
            )
            if risk_result is not None:
                m = risk_result.metrics
                portfolio_data["metrics"].update({
                    "annualized_return": float(m.annualized_return or 0),
                    "annualized_volatility": float(m.annualized_volatility or 0),
                    "sharpe_ratio": float(m.sharpe_ratio or 0),
                    "max_drawdown": float(m.max_drawdown or 0),
                })
                portfolio_data["risk"] = {
                    "metrics": m.model_dump(),
                    "return_series": risk_result.return_series.model_dump() if risk_result.return_series else {},
                }
        except Exception:
            pass

        # Try to fetch health score
        try:
            from app.services import health_service
            health_result = await health_service.calculate_portfolio_health(
                db, portfolio_id=str(portfolio_id), user_id=str(user_id)
            )
            if health_result is not None:
                portfolio_data["health"] = health_result.model_dump()
        except Exception:
            pass

        # Try to fetch optimization
        try:
            from app.services import optimization_engine
            opt_result = await optimization_engine.get_optimization_history(db, str(portfolio_id), str(user_id), limit=1)
            if opt_result:
                portfolio_data["optimization"] = opt_result[0]
        except Exception:
            pass

        # Try to fetch stress test
        try:
            from app.services import stress_testing_engine
            stress_result = await stress_testing_engine.get_stress_test_history(db, str(portfolio_id), str(user_id), limit=4)
            if stress_result:
                portfolio_data["stress"] = stress_result
        except Exception:
            pass

        return portfolio_data

    def _build_report(self, data: Dict, report_type: str) -> List:
        """Build report story (list of flowables)."""
        story = []
        portfolio = data["portfolio"]
        user = data["user"]
        holdings = data.get("holdings", [])
        metrics = data.get("metrics", {})

        # Header
        story.append(self._create_header_table(portfolio, user))  # noqa: user may be None-safe below
        story.append(Spacer(1, 20))

        # Executive Summary
        story.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        total_val = metrics.get("total_value", 0)
        total_cost = metrics.get("total_cost", 0)
        pnl = metrics.get("unrealized_pnl", 0)
        pnl_pct = metrics.get("pnl_percentage", 0)
        pnl_color = "green" if pnl >= 0 else "red"
        
        summary_text = (
            f"<b>{portfolio.name}</b> has a current value of <b>${total_val:,.2f}</b> "
            f"against a cost basis of <b>${total_cost:,.2f}</b>, representing an unrealized "
            f"<font color='{pnl_color}'><b>${pnl:,.2f} ({pnl_pct:+.2f}%)</b></font>. "
            f"The portfolio contains <b>{len(data.get('holdings', []))}</b> holdings "
            f"with a <b>{portfolio.benchmark}</b> benchmark."
        )
        story.append(Paragraph(summary_text, self.styles['BodyText2']))
        story.append(Spacer(1, 12))

        # Key Metrics
        story.append(Paragraph("Key Performance Metrics", self.styles['SectionHeader']))
        story.append(self._create_metrics_table({"metrics": metrics}))
        story.append(Spacer(1, 16))

        # Holdings Detail (for full report)
        if report_type in ["full_portfolio", "monthly_review"] and holdings:
            story.append(Paragraph("Holdings Detail", self.styles['SectionHeader']))
            story.append(self._create_holdings_table(holdings))
            story.append(Spacer(1, 16))

        # Risk Analytics
        if "risk" in data:
            story.append(Paragraph("Risk Analytics", self.styles['SectionHeader']))
            story.append(self._create_risk_table(data["risk"]))
            story.append(Spacer(1, 16))

            # Risk chart
            try:
                chart_img = generate_chart_image(
                    lambda ax: draw_valuation_chart(ax, {
                        "valuation_dates": data["risk"].get("return_series", {}).get("dates", []),
                        "valuation_values": data["risk"].get("return_series", {}).get("values", []),
                    })
                )
                story.append(Image(BytesIO(chart_img), width=6*inch, height=3*inch))
                story.append(Spacer(1, 12))
            except Exception:
                pass

        # Health Score
        if "health" in data:
            story.append(Paragraph("Portfolio Health Score", self.styles['SectionHeader']))
            story.append(self._create_health_table(data["health"]))
            story.append(Spacer(1, 16))

        # Sector Allocation
        if holdings:
            story.append(Paragraph("Sector Allocation", self.styles['SectionHeader']))
            sector_data = {}
            for h in holdings:
                sector = h.get("sector", "Unknown")
                sector_data[sector] = sector_data.get(sector, 0) + h.get("current_value", 0)
            
            try:
                chart_img = generate_chart_image(
                    lambda ax: draw_sector_pie(ax, sector_data)
                )
                story.append(Image(BytesIO(chart_img), width=4*inch, height=3*inch))
                story.append(Spacer(1, 12))
            except Exception:
                pass

        # Optimization Results
        if report_type in ["full_portfolio", "monthly_review"] and "optimization" in data:
            story.append(Paragraph("Optimization Analysis", self.styles['SectionHeader']))
            opt = data["optimization"]
            if isinstance(opt, dict) and opt.get("efficient_frontier"):
                try:
                    chart_img = generate_chart_image(
                        lambda ax: draw_efficient_frontier(ax, opt["efficient_frontier"])
                    )
                    story.append(Image(BytesIO(chart_img), width=6*inch, height=3*inch))
                    story.append(Spacer(1, 12))
                except Exception:
                    pass

        # Stress Testing
        if "stress" in data:
            story.append(Paragraph("Stress Testing Results", self.styles['SectionHeader']))
            for s in data["stress"]:
                scenario_name = s.get("scenario", "").replace("_", " ").title()
                ret = s.get("portfolio_return", 0) * 100
                dd = s.get("max_drawdown", 0) * 100
                color = "green" if ret >= 0 else "red"
                text = (
                    f"<b>{scenario_name}</b>: Portfolio would have returned "
                    f"<font color='{color}'><b>{ret:+.2f}%</b></font> "
                    f"with a maximum drawdown of <font color='red'><b>{dd:.2f}%</b></font>. "
                    f"{s.get('summary', '')}"
                )
                story.append(Paragraph(text, self.styles['BodyText2']))
            story.append(Spacer(1, 12))

        # Disclaimer
        story.append(Spacer(1, 30))
        disclaimer = (
            "<b>Disclaimer:</b> This report is for informational purposes only and does not constitute "
            "financial advice. Past performance does not guarantee future results. All data is sourced "
            "from third-party providers and may contain inaccuracies. Consult a qualified financial "
            "advisor before making investment decisions."
        )
        story.append(Paragraph(disclaimer, self.styles['Disclaimer']))

        return story

    async def generate_report(
        self,
        db: AsyncSession,
        portfolio_id: uuid.UUID,
        user_id: uuid.UUID,
        report_type: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a PDF report and return metadata."""
        portfolio_id = _to_uuid(portfolio_id)
        user_id = _to_uuid(user_id)
        report_id = uuid.uuid4()
        filename = f"{report_type}_{portfolio_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path = REPORTS_DIR / str(user_id) / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create report record
        report = Report(
            id=report_id,
            portfolio_id=portfolio_id,
            user_id=user_id,
            report_type=report_type,
            title=f"{report_type.replace('_', ' ').title()} Report",
            file_path=str(file_path),
            status="generating",
            parameters=parameters or {},
        )
        db.add(report)
        await db.commit()

        try:
            # Gather data
            data = await self._gather_report_data(db, portfolio_id, user_id, report_type)

            # Build PDF
            doc = SimpleDocTemplate(
                str(file_path),
                pagesize=letter,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch,
            )

            story = self._build_report(data, report_type)
            doc.build(story)

            # Get file size
            file_size = file_path.stat().st_size

            # Update report record
            report.status = "completed"
            report.file_size_bytes = file_size
            report.generated_at = datetime.now(timezone.utc)
            report.summary = f"Generated {report_type} report with {len(data.get('holdings', []))} holdings"
            await db.commit()

            return {
                "report_id": str(report_id),
                "status": "completed",
                "file_path": str(file_path),
                "file_size_bytes": file_size,
            }

        except Exception as e:
            report.status = "failed"
            report.error_message = str(e)
            await db.commit()
            raise


# Global instance
reporting_engine = ReportingEngine()
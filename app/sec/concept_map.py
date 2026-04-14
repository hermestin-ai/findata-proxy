"""
XBRL concept → Financial Datasets field name mapping.

Each FD field maps to an ordered list of candidate us-gaap concepts.
The first concept that has data for the requested period wins.
This handles filer-to-filer reporting differences (e.g. some companies
report `Revenues`, others `RevenueFromContractWithCustomerExcludingAssessedTax`,
others `SalesRevenueNet`).

Source references:
- https://www.sec.gov/developer (XBRL Financial Report API)
- US-GAAP Taxonomy: https://xbrl.us/xbrl-taxonomy/
"""

from __future__ import annotations

# -----------------------------------------------------------------------------
# Income Statement
# -----------------------------------------------------------------------------
INCOME_STATEMENT_MAP: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "cost_of_revenue": [
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
        "CostOfServices",
    ],
    "gross_profit": [
        "GrossProfit",
    ],
    "operating_expenses": [
        "OperatingExpenses",
        "CostsAndExpenses",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
    ],
    "net_income_common_shareholders": [
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "NetIncomeLoss",
    ],
    "earnings_per_share": [
        "EarningsPerShareBasic",
    ],
    "earnings_per_share_diluted": [
        "EarningsPerShareDiluted",
    ],
    "research_and_development": [
        "ResearchAndDevelopmentExpense",
        "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    ],
    "selling_general_and_administrative_expenses": [
        "SellingGeneralAndAdministrativeExpense",
        "GeneralAndAdministrativeExpense",
    ],
    "income_tax_expense": [
        "IncomeTaxExpenseBenefit",
    ],
    "interest_expense": [
        "InterestExpense",
        "InterestExpenseDebt",
    ],
    "weighted_average_shares": [
        "WeightedAverageNumberOfSharesOutstandingBasic",
    ],
    "weighted_average_shares_diluted": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ],
}

# -----------------------------------------------------------------------------
# Balance Sheet (instant values — reported as of a point in time)
# -----------------------------------------------------------------------------
BALANCE_SHEET_MAP: dict[str, list[str]] = {
    "total_assets": ["Assets"],
    "current_assets": ["AssetsCurrent"],
    "cash_and_equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "Cash",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "short_term_investments": [
        "MarketableSecuritiesCurrent",
        "ShortTermInvestments",
        "AvailableForSaleSecuritiesCurrent",
    ],
    "accounts_receivable": [
        "AccountsReceivableNetCurrent",
        "ReceivablesNetCurrent",
    ],
    "inventory": [
        "InventoryNet",
    ],
    "total_liabilities": ["Liabilities"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "accounts_payable": [
        "AccountsPayableCurrent",
    ],
    "short_term_debt": [
        "LongTermDebtCurrent",
        "ShortTermBorrowings",
        "DebtCurrent",
    ],
    "long_term_debt": [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
    ],
    "total_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "retained_earnings": [
        "RetainedEarningsAccumulatedDeficit",
    ],
    "property_plant_and_equipment": [
        "PropertyPlantAndEquipmentNet",
    ],
    "goodwill": [
        "Goodwill",
    ],
    "intangible_assets": [
        "IntangibleAssetsNetExcludingGoodwill",
        "FiniteLivedIntangibleAssetsNet",
    ],
}

# Computed fields for balance sheet
def compute_total_debt(row: dict) -> float | None:
    """Sum short + long term debt, treating missing as 0 only if at least one is present."""
    s = row.get("short_term_debt")
    l = row.get("long_term_debt")
    if s is None and l is None:
        return None
    return (s or 0.0) + (l or 0.0)


def compute_working_capital(row: dict) -> float | None:
    ca = row.get("current_assets")
    cl = row.get("current_liabilities")
    if ca is None or cl is None:
        return None
    return ca - cl


# -----------------------------------------------------------------------------
# Cash Flow Statement (duration values — over a period)
# -----------------------------------------------------------------------------
CASH_FLOW_MAP: dict[str, list[str]] = {
    "net_cash_flow_from_operations": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "net_cash_flow_from_investing": [
        "NetCashProvidedByUsedInInvestingActivities",
        "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations",
    ],
    "net_cash_flow_from_financing": [
        "NetCashProvidedByUsedInFinancingActivities",
        "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
    ],
    "capital_expenditure": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "depreciation_and_amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
    ],
    "share_based_compensation": [
        "ShareBasedCompensation",
    ],
    "dividends_paid": [
        "PaymentsOfDividends",
        "PaymentsOfDividendsCommonStock",
    ],
    "share_repurchases": [
        "PaymentsForRepurchaseOfCommonStock",
    ],
    "issuance_of_debt": [
        "ProceedsFromIssuanceOfLongTermDebt",
    ],
    "repayment_of_debt": [
        "RepaymentsOfLongTermDebt",
        "RepaymentsOfDebt",
    ],
    "change_in_cash": [
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
        "CashAndCashEquivalentsPeriodIncreaseDecrease",
    ],
}


def compute_free_cash_flow(row: dict) -> float | None:
    """Operating cash flow minus capex (capex is positive in XBRL, it's an outflow)."""
    ocf = row.get("net_cash_flow_from_operations")
    capex = row.get("capital_expenditure")
    if ocf is None:
        return None
    return ocf - (capex or 0.0)


# -----------------------------------------------------------------------------
# Statement type registry
# -----------------------------------------------------------------------------
STATEMENT_CONFIGS = {
    "income": {
        "map": INCOME_STATEMENT_MAP,
        "value_type": "duration",  # reported over a period
        "post_compute": {},
    },
    "balance": {
        "map": BALANCE_SHEET_MAP,
        "value_type": "instant",  # reported as of a date
        "post_compute": {
            "total_debt": compute_total_debt,
            "working_capital": compute_working_capital,
        },
    },
    "cash_flow": {
        "map": CASH_FLOW_MAP,
        "value_type": "duration",
        "post_compute": {
            "free_cash_flow": compute_free_cash_flow,
        },
    },
}

from typing import Optional


def estimate_monthly_revenue(price: Optional[float], monthly_sales: Optional[int]) -> Optional[float]:
    if price is None or monthly_sales is None:
        return None

    return round(price * monthly_sales, 2)

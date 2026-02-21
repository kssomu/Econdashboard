import os
import json
import requests
import yfinance as yf
from datetime import datetime, timedelta, timezone

# API Keys from GitHub Secrets
EODHD_API_KEY = os.environ.get("EODHD_API_KEY", "demo")
METALPRICE_API_KEY = os.environ.get("METALPRICE_API_KEY")

def get_eodhd_macro(country_iso3, indicator):
    url = f"https://eodhd.com/api/macro-indicator/{country_iso3}?api_token={EODHD_API_KEY}&fmt=json&indicator={indicator}"
    try:
        res = requests.get(url, timeout=10).json()
        if res and isinstance(res, list) and len(res) > 0:
            val = res[0]['Value']
            date = res[0]['Date'][:4] # Extract year
            if indicator == 'gdp_current_usd':
                val = f"${val / 1e9:.2f}B"
            else:
                val = f"{val:.2f}%"
            return f"{val} ({date})"
    except Exception as e:
        print(f"Error fetching EODHD macro for {country_iso3}: {e}")
    return "N/A"

def get_eodhd_bond(ticker):
    url = f"https://eodhd.com/api/eod/{ticker}.GBOND?api_token={EODHD_API_KEY}&fmt=json&order=d&limit=1"
    try:
        res = requests.get(url, timeout=10).json()
        if res and isinstance(res, list) and len(res) > 0:
            val = res[0]['close']
            date = res[0]['date']
            return f"{val:.2f}% ({date})"
    except Exception as e:
        print(f"Error fetching EODHD bond for {ticker}: {e}")
    return "N/A"

def get_yfinance_data(ticker, prefix=""):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            val = hist['Close'].iloc[-1]
            date = hist.index[-1].strftime('%Y-%m-%d')
            return f"{prefix}{val:.2f} ({date})"
    except Exception as e:
        print(f"Error fetching YFinance data for {ticker}: {e}")
    return "N/A"

def get_metal_price(symbol, fallback_ticker):
    if METALPRICE_API_KEY:
        url = f"https://api.metalpriceapi.com/v1/latest?api_key={METALPRICE_API_KEY}&base=USD&currencies={symbol}"
        try:
            res = requests.get(url, timeout=10).json()
            rate = res['rates'][symbol]
            date = datetime.fromtimestamp(res['timestamp']).strftime('%Y-%m-%d')
            price = 1 / rate
            return f"${price:.2f} ({date})"
        except Exception as e:
            print(f"Error fetching MetalPriceAPI for {symbol}: {e}")
    # Fallback to yfinance if API key is missing or request fails
    return get_yfinance_data(fallback_ticker, "$")

def main():
    # Anchor timestamp to IST
    ist = timezone(timedelta(hours=5, minutes=30))
    
    data = {
        "last_updated": datetime.now(ist).strftime("%Y-%m-%d %I:%M %p IST"),
        "table1": {
            "GDP": {
                "India": get_eodhd_macro("IND", "gdp_current_usd"),
                "US": get_eodhd_macro("USA", "gdp_current_usd"),
                "China": get_eodhd_macro("CHN", "gdp_current_usd")
            },
            "Debt to GDP": {
                "India": get_eodhd_macro("IND", "debt_percent_gdp"),
                "US": get_eodhd_macro("USA", "debt_percent_gdp"),
                "China": get_eodhd_macro("CHN", "debt_percent_gdp")
            },
            "Market Cap (Index Proxy)": {
                "India": get_yfinance_data("^NSEI"),
                "US": get_yfinance_data("^GSPC"),
                "China": get_yfinance_data("000001.SS")
            },
            "10Yr Bond": {
                "India": get_eodhd_bond("IN10Y"),
                "US": get_eodhd_bond("US10Y"),
                "China": get_eodhd_bond("CN10Y")
            }
        },
        "table2": {
            "Gold Price": get_metal_price("XAU", "GC=F"),
            "Silver Price": get_metal_price("XAG", "SI=F"),
            "Brent Crude": get_yfinance_data("BZ=F", "$")
        }
    }

    with open("data.json", "w") as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    main()
import os
import json
import requests
import yfinance as yf
from datetime import datetime, timedelta, timezone

# API Keys from GitHub Secrets
EODHD_API_KEY = os.environ.get("EODHD_API_KEY", "demo")
METALPRICE_API_KEY = os.environ.get("METALPRICE_API_KEY")

def get_worldbank_data(country_iso2, indicator, is_gdp=False):
    """Fetches macro data using the free World Bank API."""
    url = f"https://api.worldbank.org/v2/country/{country_iso2}/indicator/{indicator}?format=json&mrnev=1"
    try:
        # User-Agent header helps bypass strict datacenter blocks
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10).json()
        
        # World Bank JSON returns metadata in index 0, data in index 1
        if len(res) > 1 and res[1]:
            val = res[1][0]['value']
            date = res[1][0]['date']
            
            if val is None:
                return "N/A"
            if is_gdp:
                return f"${val / 1e9:.2f}B ({date})"
            else:
                return f"{val:.2f}% ({date})"
    except Exception as e:
        print(f"Error fetching WB data for {country_iso2}: {e}")
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
                "India": get_worldbank_data("IN", "NY.GDP.MKTP.CD", is_gdp=True),
                "US": get_worldbank_data("US", "NY.GDP.MKTP.CD", is_gdp=True),
                "China": get_worldbank_data("CN", "NY.GDP.MKTP.CD", is_gdp=True)
            },
            "Debt to GDP": {
                "India": get_worldbank_data("IN", "GC.DOD.TOTL.GD.ZS", is_gdp=False),
                "US": get_worldbank_data("US", "GC.DOD.TOTL.GD.ZS", is_gdp=False),
                "China": get_worldbank_data("CN", "GC.DOD.TOTL.GD.ZS", is_gdp=False)
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

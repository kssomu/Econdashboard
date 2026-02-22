import os
import json
import requests
import yfinance as yf
from datetime import datetime, timedelta, timezone

# API Keys from GitHub Secrets
EODHD_API_KEY = os.environ.get("EODHD_API_KEY", "demo")
METALPRICE_API_KEY = os.environ.get("METALPRICE_API_KEY")

def get_worldbank_data(country_iso2, indicator, is_gdp=False):
    """Fetches macro data using the free World Bank API and separates value/date."""
    url = f"https://api.worldbank.org/v2/country/{country_iso2}/indicator/{indicator}?format=json&mrnev=1"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10).json()
        
        if len(res) > 1 and res[1]:
            val = res[1][0]['value']
            date = res[1][0]['date']
            
            if val is None:
                return {"value": "N/A", "date": "N/A"}
            if is_gdp:
                return {"value": f"${val / 1e9:.2f}B", "date": date}
            else:
                return {"value": f"{val:.2f}%", "date": date}
    except Exception as e:
        print(f"Error fetching WB data for {country_iso2}: {e}")
    return {"value": "N/A", "date": "N/A"}

def get_eodhd_bond(ticker):
    url = f"https://eodhd.com/api/eod/{ticker}.GBOND?api_token={EODHD_API_KEY}&fmt=json&order=d&limit=1"
    try:
        res = requests.get(url, timeout=10).json()
        if res and isinstance(res, list) and len(res) > 0:
            val = res[0]['close']
            date = res[0]['date']
            return {"value": f"{val:.2f}%", "date": date}
    except Exception as e:
        print(f"Error fetching EODHD bond for {ticker}: {e}")
    return {"value": "N/A", "date": "N/A"}

def get_yfinance_data(ticker, prefix=""):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            val = hist['Close'].iloc[-1]
            date = hist.index[-1].strftime('%Y-%m-%d')
            return {"value": f"{prefix}{val:.2f}", "date": date}
    except Exception as e:
        print(f"Error fetching YFinance data for {ticker}: {e}")
    return {"value": "N/A", "date": "N/A"}

def get_metal_price(symbol, fallback_ticker):
    if METALPRICE_API_KEY:
        url = f"https://api.metalpriceapi.com/v1/latest?api_key={METALPRICE_API_KEY}&base=USD&currencies={symbol}"
        try:
            res = requests.get(url, timeout=10).json()
            rate = res['rates'][symbol]
            date = datetime.fromtimestamp(res['timestamp']).strftime('%Y-%m-%d')
            price = 1 / rate
            return {"value": f"${price:.2f}", "date": date}
        except Exception as e:
            print(f"Error fetching MetalPriceAPI for {symbol}: {e}")
    return get_yfinance_data(fallback_ticker, "$")

def main():
    ist = timezone(timedelta(hours=5, minutes=30))
    
    data = {
        "last_updated": datetime.now(ist).strftime("%Y-%m-%d %I:%M %p IST"),
        "india": [
            {"metric": "GDP", **get_worldbank_data("IN", "NY.GDP.MKTP.CD", is_gdp=True)},
            {"metric": "Debt", **get_worldbank_data("IN", "GC.DOD.TOTL.GD.ZS")},
            {"metric": "Fiscal deficit (% of GDP)", **get_worldbank_data("IN", "GC.NLD.TOTL.GD.ZS")},
            {"metric": "CPI", **get_worldbank_data("IN", "FP.CPI.TOTL.ZG")},
            {"metric": "10 yr bond yield", **get_eodhd_bond("IN10Y")},
            {"metric": "Mkt Cap NSE", **get_yfinance_data("^NSEI")}
        ],
        "us": [
            {"metric": "GDP", **get_worldbank_data("US", "NY.GDP.MKTP.CD", is_gdp=True)},
            {"metric": "Debt", **get_worldbank_data("US", "GC.DOD.TOTL.GD.ZS")},
            {"metric": "10 yr bond yield", **get_eodhd_bond("US10Y")},
            {"metric": "Mkt Cap (Index proxy)", **get_yfinance_data("^GSPC")}
        ],
        "china": [
            {"metric": "GDP", **get_worldbank_data("CN", "NY.GDP.MKTP.CD", is_gdp=True)},
            {"metric": "Debt", **get_worldbank_data("CN", "GC.DOD.TOTL.GD.ZS")},
            {"metric": "10 yr bond yield", **get_eodhd_bond("CN10Y")},
            {"metric": "Mkt Cap (Index proxy)", **get_yfinance_data("000001.SS")}
        ],
        "commodities": [
            {"metric": "Gold price", **get_metal_price("XAU", "GC=F")},
            {"metric": "Silver price", **get_metal_price("XAG", "SI=F")},
            {"metric": "Brent crude", **get_yfinance_data("BZ=F", "$")}
        ]
    }

    with open("data.json", "w") as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    main()

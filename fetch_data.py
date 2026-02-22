import os
import json
import re
import io
import requests
import yfinance as yf
import pdfplumber
from datetime import datetime, timedelta, timezone

# API Keys from GitHub Secrets
EODHD_API_KEY = os.environ.get("EODHD_API_KEY", "demo")
METALPRICE_API_KEY = os.environ.get("METALPRICE_API_KEY")

def get_worldbank_data(country_iso2, indicator, is_gdp=False):
    """Fetches macro data using the free World Bank API and separates value/date."""
    url = f"https://api.worldbank.org/v2/country/{country_iso2}/indicator/{indicator}?format=json&mrnev=1"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10).json()

        if len(res) > 1 and res[1]:
            val = res[1][0]["value"]
            date = res[1][0]["date"]

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
            val = res[0]["close"]
            date = res[0]["date"]
            return {"value": f"{val:.2f}%", "date": date}
    except Exception as e:
        print(f"Error fetching EODHD bond for {ticker}: {e}")
    return {"value": "N/A", "date": "N/A"}

def get_yfinance_data(ticker, prefix=""):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            val = hist["Close"].iloc[-1]
            date = hist.index[-1].strftime("%Y-%m-%d")
            return {"value": f"{prefix}{val:.2f}", "date": date}
    except Exception as e:
        print(f"Error fetching YFinance data for {ticker}: {e}")
    return {"value": "N/A", "date": "N/A"}

def get_metal_price(symbol, fallback_ticker):
    if METALPRICE_API_KEY:
        url = f"https://api.metalpriceapi.com/v1/latest?api_key={METALPRICE_API_KEY}&base=USD&currencies={symbol}"
        try:
            res = requests.get(url, timeout=10).json()
            rate = res["rates"][symbol]
            date = datetime.fromtimestamp(res["timestamp"]).strftime("%Y-%m-%d")
            price = 1 / rate
            return {"value": f"${price:.2f}", "date": date}
        except Exception as e:
            print(f"Error fetching MetalPriceAPI for {symbol}: {e}")
    return get_yfinance_data(fallback_ticker, "$")

def _parse_date_from_url(url):
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12
    }
    m = re.search(r"(\d{1,2})(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)(\d{2})", url, re.I)
    if m:
        day = int(m.group(1))
        mon = months[m.group(2).lower()]
        year = 2000 + int(m.group(3))
        return datetime(year, mon, day)
    m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)(\d{2})", url, re.I)
    if m:
        mon = months[m.group(1).lower()]
        year = 2000 + int(m.group(2))
        return datetime(year, mon, 1)
    return datetime.min

def _extract_cpi_from_pdf(pdf_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        pdf_bytes = requests.get(pdf_url, headers=headers, timeout=20).content
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join((page.extract_text() or "") for page in pdf.pages[:6])

        # Try to find "All India Inflation rate" with a nearby percentage
        m = re.search(r"All\s+India.*?Inflation.*?([0-9]+(?:\.[0-9]+)?)\s*%?", text, re.I | re.S)
        value = f"{float(m.group(1)):.2f}%" if m else "N/A"

        # Try to find month/year in text
        m2 = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", text, re.I)
        if m2:
            month_name = m2.group(1).title()
            year = m2.group(2)
            date_str = f"{month_name} {year}"
        else:
            # fallback to date from URL
            dt = _parse_date_from_url(pdf_url)
            date_str = dt.strftime("%Y-%m-%d") if dt != datetime.min else "N/A"

        return {"value": value, "date": date_str}
    except Exception as e:
        print(f"Error extracting CPI from PDF {pdf_url}: {e}")
    return {"value": "N/A", "date": "N/A"}

def get_mospi_cpi_latest():
    page_url = "https://www.mospi.gov.in/cpi"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        html = requests.get(page_url, headers=headers, timeout=10).text
        links = re.findall(r'href="([^"]+\.pdf)"', html, re.I)
        links = [l for l in links if "CPI" in l.upper()]

        def normalize(link):
            if link.startswith("http"):
                return link
            if link.startswith("//"):
                return "https:" + link
            if link.startswith("/"):
                return "https://www.mospi.gov.in" + link
            return "https://www.mospi.gov.in/" + link.lstrip("/")

        links = [normalize(l) for l in links]
        if not links:
            return {"value": "N/A", "date": "N/A"}

        latest_url = max(links, key=_parse_date_from_url)
        return _extract_cpi_from_pdf(latest_url)
    except Exception as e:
        print(f"Error fetching MoSPI CPI page: {e}")
    return {"value": "N/A", "date": "N/A"}

def get_brent_crude():
    # Primary: Yahoo Finance (BZ=F)
    data = get_yfinance_data("BZ=F", "$")
    if data["value"] != "N/A":
        return data

    # Fallback: Trading Economics page parse
    url = "https://tradingeconomics.com/commodity/brent-crude-oil"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        html = requests.get(url, headers=headers, timeout=10).text
        m = re.search(
            r"Brent.*?([0-9]+(?:\.[0-9]+)?)\s*USD/Bbl.*?on\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})",
            html, re.I | re.S
        )
        if m:
            price = float(m.group(1))
            date_str = m.group(2)
            date = datetime.strptime(date_str, "%B %d, %Y").strftime("%Y-%m-%d")
            return {"value": f"${price:.2f}", "date": date}
    except Exception as e:
        print(f"Error fetching Brent crude from TradingEconomics: {e}")

    return {"value": "N/A", "date": "N/A"}

def main():
    ist = timezone(timedelta(hours=5, minutes=30))

    data = {
        "last_updated": datetime.now(ist).strftime("%Y-%m-%d %I:%M %p IST"),
        "india": [
            {"metric": "GDP", **get_worldbank_data("IN", "NY.GDP.MKTP.CD", is_gdp=True)},
            {"metric": "Debt", **get_worldbank_data("IN", "GC.DOD.TOTL.GD.ZS")},
            {"metric": "Fiscal deficit (% of GDP)", **get_worldbank_data("IN", "GC.NLD.TOTL.GD.ZS")},
            {"metric": "CPI", **get_mospi_cpi_latest()},
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
            {"metric": "Brent crude", **get_brent_crude()}
        ]
    }

    with open("data.json", "w") as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    main()

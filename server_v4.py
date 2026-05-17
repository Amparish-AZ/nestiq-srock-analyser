#!/usr/bin/env python3
"""
NeStiQ Live Data Server  —  port 5000
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DATA SOURCES (100% FREE, NO API KEY NEEDED):
  1. NSE India  (nseindia.com) — official government exchange
     Live price, P/E, P/B, 52-week range — direct from exchange JSON
  2. Screener.in — most reliable free fundamentals for Indian stocks
     Balance sheet, ROE, D/E, current ratio, FCF, 5-year financials
  3. Yahoo Finance v8/chart — max history price series (fallback only)

ENDPOINTS:
  /price?tickers=TCS,INFY        -> Price + fundamentals
  /balance-sheet?tickers=TCS     -> Full balance sheet
  /sector-index?index=NIFTY_BANK -> Sector stocks
  /health                        -> Server status

Usage: python server.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json, urllib.request, urllib.error, urllib.parse
import http.server, socketserver, gzip, time, re, threading, datetime
from urllib.parse import urlparse, parse_qs

PORT = 5000

# ── Sector index constituents ──────────────────────────────────────────────────
SECTOR_INDICES = {
    "NIFTY_BANK":   ["HDFCBANK","ICICIBANK","SBIN","AXISBANK","KOTAKBANK","INDUSINDBK",
                     "BAJFINANCE","BAJAJFINSV","BANDHANBNK","FEDERALBNK","IDFCFIRSTB",
                     "PNB","BANKBARODA","CANARABANK"],
    "NIFTY_IT":     ["TCS","INFY","WIPRO","HCLTECH","TECHM","LTIM",
                     "MPHASIS","COFORGE","PERSISTENT","OFSS"],
    "NIFTY_PHARMA": ["SUNPHARMA","DRREDDY","CIPLA","DIVISLAB","APOLLOHOSP","BIOCON",
                     "AUROPHARMA","LUPIN","TORNTPHARM","ABBOTINDIA"],
    "NIFTY_FMCG":   ["HINDUNILVR","ITC","NESTLEIND","ASIANPAINT","TITAN","TATACONSUM",
                     "DABUR","MARICO","GODREJCP","BRITANNIA","TRENT"],
    "NIFTY_AUTO":   ["MARUTI","TATAMOTORS","M&M","BAJAJ-AUTO","HEROMOTOCO","EICHERMOT",
                     "TVSMOTOR","ASHOKLEY","BALKRISIND","BOSCHLTD","MOTHERSON"],
    "NIFTY_METAL":  ["TATASTEEL","JSWSTEEL","HINDALCO","COALINDIA","VEDL","NMDC",
                     "SAIL","NATIONALUM","HINDCOPPER","WELCORP","APL"],
}

# ── NSE session cookie cache ───────────────────────────────────────────────────
_nse_lock    = threading.Lock()
_nse_session = {"cookies": None, "fetched_at": 0}
NSE_TTL      = 600   # refresh every 10 min

# ── Screener.in cache (30 min per ticker) ─────────────────────────────────────
_screener_cache = {}
SCREENER_TTL    = 1800

# ── Yahoo crumb cache ─────────────────────────────────────────────────────────
_yahoo_crumb = {"crumb": None, "cookie": None, "ts": 0}
_yahoo_lock  = threading.Lock()
YAHOO_TTL    = 3600

# Screener slug overrides (ticker → screener URL slug)
SCREENER_SLUGS = {
    "M&M":"mahindra-and-mahindra","BAJAJ-AUTO":"bajaj-auto",
    "HDFCBANK":"hdfc-bank","ICICIBANK":"icici-bank",
    "KOTAKBANK":"kotak-mahindra-bank","AXISBANK":"axis-bank",
    "INDUSINDBK":"indusind-bank","BAJFINANCE":"bajaj-finance",
    "BAJAJFINSV":"bajaj-finserv","BANDHANBNK":"bandhan-bank",
    "FEDERALBNK":"federal-bank","IDFCFIRSTB":"idfc-first-bank",
    "BANKBARODA":"bank-of-baroda","CANARABANK":"canara-bank",
    "HINDUNILVR":"hindustan-unilever","NESTLEIND":"nestle-india",
    "ASIANPAINT":"asian-paints","TATACONSUM":"tata-consumer-products",
    "GODREJCP":"godrej-consumer-products","TATAMOTORS":"tata-motors",
    "HEROMOTOCO":"hero-motocorp","EICHERMOT":"eicher-motors",
    "TVSMOTOR":"tvs-motor-company","ASHOKLEY":"ashok-leyland",
    "BALKRISIND":"balkrishna-industries","BOSCHLTD":"bosch",
    "MOTHERSON":"samvardhana-motherson-international",
    "TATASTEEL":"tata-steel","JSWSTEEL":"jsw-steel",
    "HINDALCO":"hindalco-industries","COALINDIA":"coal-india",
    "NATIONALUM":"national-aluminium-company","HINDCOPPER":"hindustan-copper",
    "SUNPHARMA":"sun-pharmaceutical-industries",
    # DRREDDY fix — screener uses "dr-reddys-laboratories" (no apostrophe-s issue)
    "DRREDDY":"dr-reddys-laboratories",
    "CIPLA":"cipla",
    "DIVISLAB":"divis-laboratories",
    "APOLLOHOSP":"apollo-hospitals-enterprise","AUROPHARMA":"aurobindo-pharma",
    "TORNTPHARM":"torrent-pharmaceuticals","ABBOTINDIA":"abbott-india",
    "LUPIN":"lupin","BIOCON":"biocon",
    "HCLTECH":"hcl-technologies","OFSS":"oracle-financial-services-software",
    "PERSISTENT":"persistent-systems","LTIM":"ltimindtree",
    "MPHASIS":"mphasis","COFORGE":"coforge",
    "POWERGRID":"power-grid-corporation-of-india",
    "ADANIENT":"adani-enterprises","GRASIM":"grasim-industries",
    "SHREECEM":"shree-cement","ULTRACEMCO":"ultratech-cement",
    "BRITANNIA":"britannia-industries","DABUR":"dabur-india",
    "TITAN":"titan-company","TRENT":"trent",
    "NTPC":"ntpc","ONGC":"oil-and-natural-gas-corporation",
    "BPCL":"bharat-petroleum-corporation",
    "IOC":"indian-oil-corporation","RELIANCE":"reliance-industries",
    "WIPRO":"wipro","INFY":"infosys","TCS":"tata-consultancy-services",
    "SBIN":"state-bank-of-india","LT":"larsen-and-toubro",
    "TECHM":"tech-mahindra","PNB":"punjab-national-bank",
    "ITC":"itc","MARUTI":"maruti-suzuki-india",
    "ADANIPORTS":"adani-ports-and-special-economic-zone",
    "HDFCLIFE":"hdfc-life-insurance-company",
    "SBILIFE":"sbi-life-insurance-company",
    "MARICO":"marico","NMDC":"nmdc",
    "SAIL":"steel-authority-of-india","WELCORP":"welspun-corp",
    "APL":"apl-apollo-tubes","VEDL":"vedanta",
    # Additional common tickers
    "ZOMATO":"zomato","PAYTM":"one-97-communications",
    "NYKAA":"fsh","DMART":"avenue-supermarts",
    "PIDILITIND":"pidilite-industries","BERGEPAINT":"berger-paints-india",
    "HAVELLS":"havells-india","VOLTAS":"voltas",
    "MCDOWELL-N":"united-spirits","UBL":"united-breweries",
    "RECLTD":"rec","PFC":"power-finance-corporation",
    "IRCTC":"indian-railway-catering-and-tourism-corporation",
    "LICI":"life-insurance-corporation-of-india",
    "CGPOWER":"cg-power-and-industrial-solutions",
}


# ──────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

def _fetch(url, headers=None, timeout=18):
    h = {
        "User-Agent":      UA,
        "Accept":          "application/json,text/html,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection":      "keep-alive",
    }
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if "gzip" in r.headers.get("Content-Encoding", ""):
            raw = gzip.decompress(raw)
        return raw.decode("utf-8", errors="ignore"), r

def _safe(v, d=2):
    try:
        f = float(v)
        return None if (f != f or abs(f) > 1e15) else round(f, d)
    except Exception:
        return None

def _num(s):
    if s is None:
        return None
    try:
        return float(str(s).replace(",", "").replace("₹", "").strip() or "x")
    except Exception:
        return None

def _cr(val):
    """Format Crore value to readable string."""
    if val is None:
        return "N/A"
    return f"₹{val/100:.1f}K Cr" if abs(val) >= 1000 else f"₹{val:.1f} Cr"


# ──────────────────────────────────────────────────────────────────────────────
# SOURCE 1 — NSE INDIA (official exchange website JSON)
# ──────────────────────────────────────────────────────────────────────────────

def _get_nse_cookies():
    """Establish NSE India browser session. Returns cookie string."""
    with _nse_lock:
        now = time.time()
        s   = _nse_session
        if s["cookies"] and (now - s["fetched_at"]) < NSE_TTL:
            return s["cookies"]

        print("  [NSE] Establishing session…")
        try:
            cookies = {}

            # NSE requires full browser-like headers to avoid 403
            browser_headers = {
                "User-Agent":      UA,
                "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection":      "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest":  "document",
                "Sec-Fetch-Mode":  "navigate",
                "Sec-Fetch-Site":  "none",
                "Sec-Fetch-User":  "?1",
                "Cache-Control":   "max-age=0",
                "Referer":         "https://www.google.co.in/",
            }

            # Step 1: Load homepage to get initial cookies
            req1 = urllib.request.Request("https://www.nseindia.com/", headers=browser_headers)
            with urllib.request.urlopen(req1, timeout=15) as r1:
                raw = r1.read()
                for part in r1.headers.get("Set-Cookie", "").split(","):
                    kv = part.strip().split(";")[0]
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        cookies[k.strip()] = v.strip()

            if not cookies:
                print("  [NSE] No cookies from homepage")
                return None

            time.sleep(1.2)  # Mimic human browsing delay

            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())

            # Step 2: Load quotes page with cookies (sets more session cookies)
            req2 = urllib.request.Request(
                "https://www.nseindia.com/get-quotes/equity?symbol=RELIANCE",
                headers={**browser_headers,
                         "Cookie":  cookie_str,
                         "Referer": "https://www.nseindia.com/"})
            with urllib.request.urlopen(req2, timeout=15) as r2:
                for part in r2.headers.get("Set-Cookie", "").split(","):
                    kv = part.strip().split(";")[0]
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        cookies[k.strip()] = v.strip()

            time.sleep(0.8)

            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
            if cookie_str:
                s["cookies"]    = cookie_str
                s["fetched_at"] = now
                print(f"  [NSE] Session ready ({len(cookies)} cookies)")
                return cookie_str

        except urllib.error.HTTPError as e:
            print(f"  [NSE] Session error: HTTP {e.code} — NSE is blocking requests. "
                  f"Using Yahoo Finance as price source.")
        except Exception as e:
            print(f"  [NSE] Session error: {e}")
        return None


def fetch_nse_quote(ticker):
    """Live quote from NSE India official API (nseindia.com/api/quote-equity)."""
    cookies = _get_nse_cookies()
    if not cookies:
        return None

    sym = urllib.parse.quote(ticker)
    try:
        text, _ = _fetch(
            f"https://www.nseindia.com/api/quote-equity?symbol={sym}",
            headers={
                "Referer":          f"https://www.nseindia.com/get-quotes/equity?symbol={sym}",
                "X-Requested-With": "XMLHttpRequest",
                "Cookie":           cookies,
                "Accept":           "application/json, */*",
            },
            timeout=12
        )
        d   = json.loads(text)
        pi  = d.get("priceInfo", {})
        meta= d.get("metadata",  {})
        ind = d.get("industryInfo", {})
        sec = d.get("securityInfo",  {})
        whl = pi.get("weekHighLow", {})

        ltp  = _safe(pi.get("lastPrice") or pi.get("close"))
        prev = _safe(pi.get("previousClose"))
        chg  = round((ltp - prev) / prev * 100, 2) if ltp and prev and prev > 0 else None

        # P/E: NSE returns it in pdSymbolPe key at top level
        pe = _safe(d.get("pdSymbolPe") or meta.get("pdSymbolPe"))

        print(f"  [NSE] {ticker}: ₹{ltp}  chg={chg}%  PE={pe}  52W {whl.get('min')}–{whl.get('max')}")
        return {
            "price":      ltp,
            "prev_close": prev,
            "change_pct": chg,
            "year_high":  _safe(whl.get("max")),
            "year_low":   _safe(whl.get("min")),
            "pe":         pe,
            "pb":         None,  # NSE doesn't give P/B directly in this endpoint
            "company":    meta.get("companyName", ticker),
            "industry":   ind.get("industry", ""),
            "sector":     ind.get("sector", ""),
            "source":     "nse_official",
        }
    except Exception as e:
        print(f"  [NSE] {ticker}: {e}")
        if "403" in str(e) or "401" in str(e):
            with _nse_lock:
                _nse_session["cookies"] = None
        return None


def fetch_nse_history(ticker):
    """1-year daily close prices from NSE India historical data API."""
    cookies = _get_nse_cookies()
    if not cookies:
        return []

    sym   = urllib.parse.quote(ticker)
    end   = datetime.date.today()
    start = end - datetime.timedelta(days=375)
    s_str = start.strftime("%d-%m-%Y")
    e_str = end.strftime("%d-%m-%Y")

    url = (f"https://www.nseindia.com/api/historical/cm/equity"
           f"?symbol={sym}&series=[%22EQ%22]&from={s_str}&to={e_str}&csv=false")
    try:
        text, _ = _fetch(url, headers={
            "Referer":          f"https://www.nseindia.com/get-quotes/equity?symbol={sym}",
            "X-Requested-With": "XMLHttpRequest",
            "Cookie":           cookies,
            "Accept":           "application/json, */*",
        }, timeout=15)
        rows    = json.loads(text).get("data", [])
        history = []
        for row in rows:
            try:
                d   = datetime.datetime.strptime(row.get("CH_TIMESTAMP",""), "%Y-%m-%d")
                p   = _safe(row.get("CH_CLOSING_PRICE"))
                if p and p > 0:
                    history.append({"date": int(d.timestamp() * 1000), "price": p})
            except Exception:
                pass
        history.sort(key=lambda x: x["date"])
        print(f"  [NSE] {ticker} history: {len(history)} days")
        return history
    except Exception as e:
        print(f"  [NSE] {ticker} history: {e}")
        return []


# ──────────────────────────────────────────────────────────────────────────────
# SOURCE 2 — SCREENER.IN (fundamentals + balance sheet)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_screener(ticker):
    """Fetch and parse Screener.in company page for fundamentals + financials."""
    now = time.time()
    if ticker in _screener_cache and (now - _screener_cache[ticker]["ts"]) < SCREENER_TTL:
        return _screener_cache[ticker]["data"]

    base_slug = SCREENER_SLUGS.get(ticker, ticker.lower()
                               .replace("&","-").replace(".","-").replace(" ","-"))

    # Build a list of slug variants to try (handles apostrophes, special chars, etc.)
    slug_variants = [base_slug]
    # Try without special chars
    clean = re.sub(r"[^a-z0-9-]", "", base_slug)
    if clean != base_slug:
        slug_variants.append(clean)
    # Try replacing "s-" patterns (apostrophe-s issues like dr-reddy-s -> dr-reddys)
    if "-s-" in base_slug:
        slug_variants.append(base_slug.replace("-s-", "s-"))
    if base_slug.endswith("-s"):
        slug_variants.append(base_slug[:-2] + "s")
    # Try ticker directly as slug (lowercase)
    slug_variants.append(ticker.lower().replace("&","").replace("-","").replace(".",""))

    for slug in slug_variants:
        for suffix in ["consolidated/", ""]:
            url = f"https://www.screener.in/company/{slug}/{suffix}"
            try:
                text, _ = _fetch(url, headers={
                    "Referer": "https://www.screener.in/",
                    "Accept":  "text/html,*/*",
                }, timeout=22)

                # Screener returns 200 with "Page not found" text for missing pages
                if ("Page not found" in text or
                    "404" in text[:300] or
                    len(text) < 2000):
                    continue

                data = _parse_screener(text, ticker)
                if data and (data.get("pe") or data.get("roe") or data.get("income_statement")):
                    _screener_cache[ticker] = {"data": data, "ts": now}
                    print(f"  [Screener] {ticker}: PE={data.get('pe')}  "
                          f"ROE={data.get('roe')}%  D/E={data.get('de')}  (slug={slug})")
                    return data
                else:
                    print(f"  [Screener] {ticker}: parsed but no data at {url}")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue  # try next variant silently
                print(f"  [Screener] {ticker} {url}: HTTP {e.code}")
            except Exception as e:
                print(f"  [Screener] {ticker} {url}: {e}")

    print(f"  [Screener] {ticker}: not found (tried {slug_variants})")
    return None


def _parse_screener(html, ticker):
    """Extract all financial data from Screener.in HTML.
    Handles multiple Screener HTML versions (2022, 2023, 2024+).
    """
    result = {"ticker": ticker, "source": "screener.in"}

    # Company name
    m = re.search(r'<h1[^>]*>\s*([^<\n]+)\s*</h1>', html)
    if m:
        result["company_name"] = m.group(1).strip()

    # ── DEBUG: log a snippet to see actual structure ──
    # (uncomment locally if ratios still fail)
    # idx = html.lower().find("stock p/e")
    # if idx >= 0: print("  [DBG]", repr(html[idx:idx+300]))

    # ══════════════════════════════════════════════════════
    # KEY RATIOS — Screener renders them in several layouts:
    #
    # Layout A (classic, pre-2024):
    #   <li><span class="name">Stock P/E</span>
    #       <span class="nowrap value">42.3</span></li>
    #
    # Layout B (2023 redesign):
    #   <li class="flex flex-space-between">
    #       <span>Stock P/E</span>
    #       <span class="number">42.3</span></li>
    #
    # Layout C (2024+ with data attributes):
    #   <li><span>Stock P/E</span>
    #       <span id="..." data-source="...">42.3</span></li>
    #
    # Layout D (inline ratio cards):
    #   "Stock P/E":"42.3"  (JSON-ld / inline script)
    #
    # We try all patterns; first match wins.
    # ══════════════════════════════════════════════════════

    def _extract_ratio(html, *label_variants):
        """Try many patterns to extract a ratio after a label."""
        for label in label_variants:
            label_esc = re.escape(label)

            # Pattern A — classic span.name / span.value
            m = re.search(
                rf'<span[^>]*>\s*{label_esc}\s*</span>\s*<span[^>]*>\s*([\d,. ]+)\s*</span>',
                html, re.IGNORECASE | re.DOTALL)
            if m:
                v = _num(m.group(1))
                if v is not None: return v

            # Pattern B — <li> with label then number span
            m = re.search(
                rf'<li[^>]*>.*?{label_esc}.*?<span[^>]*class=["\'][^"\']*(?:number|value|nowrap)[^"\']*["\'][^>]*>\s*([\d,.]+)\s*</span>',
                html, re.IGNORECASE | re.DOTALL)
            if m:
                v = _num(m.group(1))
                if v is not None: return v

            # Pattern C — any span after label within 600 chars
            idx = html.lower().find(label.lower())
            if idx >= 0:
                chunk = html[idx:idx+600]
                # Find the next standalone number (not inside a tag attribute)
                for nm in re.finditer(r'>\s*([\d]+(?:[,.][\d]+)*)\s*<', chunk):
                    v = _num(nm.group(1))
                    if v is not None and v > 0: return v

            # Pattern D — JSON-style "Label":"value" or "Label":value
            m = re.search(
                rf'["\']?{label_esc}["\']?\s*[:\-]\s*["\']?([\d,.]+)["\']?',
                html, re.IGNORECASE)
            if m:
                v = _num(m.group(1))
                if v is not None: return v

        return None

    # ── Extract each ratio using multiple label variants ──
    result["pe"]   = _extract_ratio(html, "Stock P/E", "P/E Ratio", "P/E", "PE Ratio", "Price to Earnings")
    result["pb"]   = _extract_ratio(html, "Price to Book", "P/B Ratio", "P/B", "Price/Book")
    result["roe"]  = _extract_ratio(html, "Return on equity", "Return on Equity", "ROE %", "ROE")
    result["roce"] = _extract_ratio(html, "ROCE", "Return on Capital Employed", "ROCE %")
    result["de"]   = _extract_ratio(html, "Debt to equity", "Debt / Equity", "D/E Ratio", "Debt to Equity")
    result["cr"]   = _extract_ratio(html, "Current ratio", "Current Ratio")
    result["eps"]  = _extract_ratio(html, "EPS in Rs", "EPS", "Earnings Per Share")

    # Log what we found for debugging
    print(f"  [Screener] {ticker} ratios: PE={result['pe']} ROE={result['roe']}% "
          f"PB={result['pb']} D/E={result['de']} ROCE={result['roce']}")

    # ── Financial tables ──
    result["income_statement"] = _parse_table(html, ["profit-loss", "Profit & Loss", "profit &amp; loss", "Profit Loss"])
    result["balance_sheet"]    = _parse_table(html, ["balance-sheet", "Balance Sheet", "balancesheet"])
    result["cash_flow"]        = _parse_table(html, ["cash-flow", "Cash Flows", "cash flow", "cashflow"])

    # ── Derived metrics from income/cash-flow tables ──
    pl = result["income_statement"]
    cf = result["cash_flow"]

    rev_s = _get_row(pl, "Sales", "Revenue", "Net Sales", "Total Revenue", "Revenue from Operations")
    ni_s  = _get_row(pl, "Net Profit", "Profit after tax", "PAT", "Net profit", "Profit After Tax")
    op_s  = _get_row(pl, "Operating Profit", "EBIT", "EBITDA", "OPM", "Operating Profit / Loss")
    ie_s  = _get_row(pl, "Interest", "Interest expense", "Finance costs", "Finance Cost")
    ocf_s = _get_row(cf, "Cash from Operations", "Cash from operating activity",
                     "Net Cash from Operating Activities", "Operating Activities")
    cap_s = _get_row(cf, "Capital Expenditure", "Capex", "Purchase of fixed assets",
                     "Purchase of Property", "Additions to Fixed Assets")

    if rev_s and len(rev_s) >= 2 and rev_s[0] and rev_s[1] and rev_s[1] > 0:
        result["rg"] = round((rev_s[0] - rev_s[1]) / rev_s[1] * 100, 1)

    if rev_s and ni_s and rev_s[0] and ni_s[0] and rev_s[0] > 0:
        result["pm"] = round(ni_s[0] / rev_s[0] * 100, 1)

    if op_s and ie_s and op_s[0] and ie_s[0] and ie_s[0] != 0:
        result["interest_coverage"] = _safe(abs(op_s[0] / ie_s[0]), 1)

    if ocf_s and ocf_s[0] is not None and cap_s and cap_s[0] is not None:
        fcf = ocf_s[0] - abs(cap_s[0])
        result["fcf_cr"] = fcf
        if rev_s and rev_s[0] and rev_s[0] > 0:
            result["fcf_margin"] = round(fcf / rev_s[0] * 100, 1)

    # ── If PE/ROE still None, try computing ROE from tables ──
    if result.get("roe") is None:
        bs = result.get("balance_sheet", {})
        eq_s  = _get_row(bs, "Equity Capital", "Shareholders Equity", "Net Worth", "Total Equity")
        res_s = _get_row(bs, "Reserves", "Reserves & Surplus", "Reserves and Surplus")
        if ni_s and ni_s[0] and eq_s and eq_s[0]:
            eq_val  = eq_s[0]
            res_val = res_s[0] if (res_s and res_s[0]) else 0
            net_eq  = eq_val + res_val
            if net_eq > 0:
                result["roe"] = round(ni_s[0] / net_eq * 100, 1)
                print(f"  [Screener] {ticker}: ROE computed from tables = {result['roe']}%")

    return result


def _parse_table(html, id_variants):
    """Find and parse a financial table by its section id/heading."""
    table_html = None
    for variant in id_variants:
        # Try by section id
        m = re.search(
            rf'id=["\'](?:[^"\']*{re.escape(variant.lower())}[^"\']*)["\'].*?<table[^>]*>(.*?)</table>',
            html, re.DOTALL | re.IGNORECASE
        )
        if m:
            table_html = m.group(1)
            break
        # Try by heading text
        idx = html.lower().find(variant.lower())
        if idx >= 0:
            chunk = html[max(0,idx-200):idx+15000]
            tm = re.search(r'<table[^>]*>(.*?)</table>', chunk, re.DOTALL)
            if tm:
                table_html = tm.group(1)
                break

    if not table_html:
        return {}

    # Parse years from th elements
    years = re.findall(r'<th[^>]*>\s*([A-Z][a-z]{2}\s*\d{2,4})\s*</th>', table_html)

    # Parse data rows
    data  = {"years": years}
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL):
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) < 2:
            continue
        label = re.sub(r'<[^>]+>', '', cells[0]).strip()
        if not label or label == "+":
            continue
        vals = [_num(re.sub(r'<[^>]+>', '', c).strip()) for c in cells[1:]]
        if label:
            data[label] = vals
    return data


def _get_row(table, *keys):
    """Get first matching row from parsed table dict."""
    if not table:
        return None
    for k in keys:
        if k in table and table[k]:
            return table[k]
    # Case-insensitive fallback
    k_lower = {k.lower(): v for k, v in table.items() if k != "years"}
    for key in keys:
        v = k_lower.get(key.lower())
        if v:
            return v
    return None


def _screener_to_api(ticker, sd):
    """Format Screener data into the API response shape the HTML expects."""
    if not sd:
        return None

    pl = sd.get("income_statement", {})
    bs = sd.get("balance_sheet",    {})
    cf = sd.get("cash_flow",        {})
    yr_pl = pl.get("years", [])
    yr_bs = bs.get("years", [])
    yr_cf = cf.get("years", [])

    def g(src, *keys):
        return _get_row(src, *keys) or []

    def fmt_inc(i):
        y  = yr_pl[i] if i < len(yr_pl) else "N/A"
        rs = g(pl,"Sales","Revenue","Net Sales","Total Revenue")
        gp = g(pl,"Operating Profit","Gross Profit","EBITDA")
        ni = g(pl,"Net Profit","Profit after tax","PAT")
        return {
            "year":        y,
            "revenue":     _cr(rs[i]) if i < len(rs) else "N/A",
            "gross_profit":_cr(gp[i]) if i < len(gp) else "N/A",
            "ebit":        _cr(gp[i]) if i < len(gp) else "N/A",
            "net_income":  _cr(ni[i]) if i < len(ni) else "N/A",
        }

    def fmt_bs(i):
        y   = yr_bs[i] if i < len(yr_bs) else "N/A"
        ta  = g(bs,"Total Assets","Assets")
        tl  = g(bs,"Total Liabilities","Liabilities")
        eq  = g(bs,"Equity Capital","Shareholders Equity")
        res = g(bs,"Reserves","Reserves & Surplus","Reserves and Surplus")
        bor = g(bs,"Borrowings","Total Debt","Long Term Borrowings")
        cas = g(bs,"Cash Equivalents","Cash & Bank Balances","Cash")
        ca  = g(bs,"Current Assets","Total Current Assets")
        cl  = g(bs,"Current Liabilities","Total Current Liabilities")
        # Equity = equity capital + reserves
        eq_val  = (eq[i]  if i < len(eq)  else None) or 0
        res_val = (res[i] if i < len(res) else None) or 0
        tot_eq  = eq_val + res_val if (eq_val or res_val) else None
        return {
            "year":             y,
            "total_assets":     _cr(ta[i])  if i < len(ta)  else "N/A",
            "total_liabilities":_cr(tl[i])  if i < len(tl)  else "N/A",
            "equity":           _cr(tot_eq),
            "cash":             _cr(cas[i]) if i < len(cas) else "N/A",
            "total_debt":       _cr(bor[i]) if i < len(bor) else "N/A",
            "current_assets":   _cr(ca[i])  if i < len(ca)  else "N/A",
            "current_liab":     _cr(cl[i])  if i < len(cl)  else "N/A",
        }

    def fmt_cf(i):
        y    = yr_cf[i] if i < len(yr_cf) else "N/A"
        ocf  = g(cf,"Cash from Operations","Cash from operating activity","Net Cash from Operating Activities")
        capx = g(cf,"Capital Expenditure","Capex","Purchase of fixed assets")
        ocf_v  = ocf[i]  if i < len(ocf)  else None
        capx_v = capx[i] if i < len(capx) else None
        fcf    = (ocf_v - abs(capx_v)) if ocf_v is not None and capx_v is not None else None
        return {
            "year":         y,
            "operating_cf": _cr(ocf_v),
            "free_cashflow":_cr(fcf),
            "capex":        _cr(capx_v),
        }

    n_pl = min(5, len(yr_pl))
    n_bs = min(5, len(yr_bs))
    n_cf = min(5, len(yr_cf))

    return {
        "ticker":  ticker,
        "company": sd.get("company_name", ticker),
        "sector":  "",
        "industry":"",
        "source":  "screener.in",
        "ratios": {
            "pe":                sd.get("pe"),
            "pb":                sd.get("pb"),
            "de_ratio":          sd.get("de"),
            "current_ratio":     sd.get("cr"),
            "net_margin_pct":    sd.get("pm"),
            "roa_pct":           None,
            "interest_coverage": sd.get("interest_coverage"),
            "fcf_margin_pct":    sd.get("fcf_margin"),
            "revenue_growth_pct":sd.get("rg"),
            "roe_pct":           sd.get("roe"),
            "roce_pct":          sd.get("roce"),
        },
        "income_statement": [fmt_inc(i) for i in range(n_pl)],
        "balance_sheet":    [fmt_bs(i)  for i in range(n_bs)],
        "cash_flow":        [fmt_cf(i)  for i in range(n_cf)],
    }


# ──────────────────────────────────────────────────────────────────────────────
# SOURCE 3 — YAHOO FINANCE (price history + fundamentals fallback)
# ──────────────────────────────────────────────────────────────────────────────

def _get_yahoo_crumb():
    """Get Yahoo Finance crumb + cookie. Uses multiple methods as fc.yahoo.com is deprecated."""
    with _yahoo_lock:
        now = time.time()
        d   = _yahoo_crumb
        if d["crumb"] and (now - d["ts"]) < YAHOO_TTL:
            return d["crumb"], d["cookie"]

        print("  [Yahoo] Refreshing crumb…")

        # Method 1: Direct crumb endpoint (works without cookie on some regions)
        try:
            ct, _ = _fetch(
                "https://query1.finance.yahoo.com/v1/test/getcrumb",
                headers={"Accept": "text/plain,*/*"},
                timeout=10
            )
            crumb = ct.strip()
            if crumb and len(crumb) >= 5 and "<" not in crumb and "error" not in crumb.lower():
                d["crumb"] = crumb; d["cookie"] = ""; d["ts"] = now
                print(f"  [Yahoo] crumb OK (method 1: no-cookie)")
                return crumb, ""
        except Exception as e:
            print(f"  [Yahoo] crumb method 1: {e}")

        # Method 2: Load finance.yahoo.com to get cookie, then get crumb
        try:
            _, resp = _fetch(
                "https://finance.yahoo.com/",
                headers={"Accept": "text/html,*/*", "Referer": "https://www.google.com/"},
                timeout=12
            )
            # Parse cookies from response
            raw_cookies = resp.headers.get("Set-Cookie", "")
            ck_parts = []
            for part in raw_cookies.split(","):
                kv = part.strip().split(";")[0].strip()
                if "=" in kv and kv:
                    ck_parts.append(kv)
            ck = "; ".join(ck_parts)

            if ck:
                time.sleep(0.3)
                ct, _ = _fetch(
                    "https://query1.finance.yahoo.com/v1/test/getcrumb",
                    headers={"Cookie": ck, "Accept": "text/plain,*/*"},
                    timeout=10
                )
                crumb = ct.strip()
                if crumb and len(crumb) >= 5 and "<" not in crumb and "error" not in crumb.lower():
                    d["crumb"] = crumb; d["cookie"] = ck; d["ts"] = now
                    print(f"  [Yahoo] crumb OK (method 2: finance.yahoo.com cookie)")
                    return crumb, ck
        except Exception as e:
            print(f"  [Yahoo] crumb method 2: {e}")

        # Method 3: Try query2 fallback
        try:
            ct, _ = _fetch(
                "https://query2.finance.yahoo.com/v1/test/getcrumb",
                headers={"Accept": "text/plain,*/*"},
                timeout=10
            )
            crumb = ct.strip()
            if crumb and len(crumb) >= 5 and "<" not in crumb:
                d["crumb"] = crumb; d["cookie"] = ""; d["ts"] = now
                print(f"  [Yahoo] crumb OK (method 3: query2)")
                return crumb, ""
        except Exception as e:
            print(f"  [Yahoo] crumb method 3: {e}")

        print("  [Yahoo] All crumb methods failed")
        return None, None


def fetch_yahoo_history(ticker):
    """Max history from Yahoo Finance chart API (weekly candles since IPO)."""
    sym = ticker + ".NS"
    for base in ["query1", "query2"]:
        try:
            text, _ = _fetch(
                f"https://{base}.finance.yahoo.com/v8/finance/chart/{sym}"
                f"?interval=1wk&range=max&events=history",
                headers={"Accept": "application/json"}
            )
            res  = json.loads(text)["chart"]["result"][0]
            meta = res["meta"]
            closes = res["indicators"]["quote"][0].get("close",[])
            tss    = res.get("timestamp",[])
            hist   = [{"date": ts*1000, "price": round(p,2)}
                      for ts,p in zip(tss,closes) if p and p>0]
            live   = meta.get("regularMarketPrice") or meta.get("previousClose")
            if not live and hist:
                live = hist[-1]["price"]
            name = meta.get("longName") or meta.get("shortName", ticker)
            pe   = _safe(meta.get("trailingPE"))
            print(f"  [Yahoo] {ticker}: ₹{live}  {len(hist)} weeks history")
            return _safe(live), hist, name, pe
        except Exception as e:
            print(f"  [Yahoo] {ticker} [{base}]: {e}")
    return None, [], ticker, None


def _yahoo_balance_sheet(ticker):
    """Yahoo Finance balance sheet — uses v8/quoteSummary (v10 is deprecated)."""
    sym    = ticker + ".NS"
    crumb, cookie = _get_yahoo_crumb()

    mods = ("incomeStatementHistory,balanceSheetHistory,"
            "cashflowStatementHistory,defaultKeyStatistics,"
            "financialData,summaryDetail,assetProfile")

    # Try v8 first (current), then v11 (newer), then v10 (legacy)
    for version in ["v8", "v11", "v10"]:
        for base in ["query1", "query2"]:
            try:
                if crumb:
                    url = (f"https://{base}.finance.yahoo.com/{version}/finance/quoteSummary/{sym}"
                           f"?modules={mods}&crumb={urllib.parse.quote(crumb)}")
                    hdrs = {"Cookie": cookie or "", "Accept": "application/json",
                            "Referer": f"https://finance.yahoo.com/quote/{sym}"}
                else:
                    # Try without crumb — sometimes works for basic data
                    url = (f"https://{base}.finance.yahoo.com/{version}/finance/quoteSummary/{sym}"
                           f"?modules={mods}")
                    hdrs = {"Accept": "application/json",
                            "Referer": f"https://finance.yahoo.com/quote/{sym}"}

                text, _ = _fetch(url, headers=hdrs, timeout=20)
                data = json.loads(text)

                err = data.get("quoteSummary", {}).get("error")
                if err:
                    desc = err.get("description", "") if isinstance(err, dict) else str(err)
                    if "401" in desc or "Invalid Crumb" in desc:
                        with _yahoo_lock:
                            _yahoo_crumb["crumb"] = None
                    print(f"  [Yahoo] {ticker} {version}/{base} error: {desc}")
                    continue

                result_list = data.get("quoteSummary", {}).get("result")
                if not result_list:
                    continue

                qr = result_list[0]
                print(f"  [Yahoo] {ticker}: balance sheet OK ({version}/{base})")

                def rv(d, *keys):
                    for k in keys:
                        v = d.get(k)
                        if v is None: continue
                        if isinstance(v, dict):
                            r = v.get("raw")
                            if r is not None: return r
                        elif isinstance(v, (int, float)) and v == v: return v
                    return None

                fd = qr.get("financialData",{});   ks = qr.get("defaultKeyStatistics",{})
                sd = qr.get("summaryDetail",{});    ap = qr.get("assetProfile",{})

                def parse_stmts(key, subkey, fields):
                    rows = []
                    for s in qr.get(key,{}).get(subkey,[])[:3]:
                        yr = s.get("endDate",{}).get("fmt","N/A") if isinstance(s.get("endDate"),dict) else str(s.get("endDate","N/A"))
                        row = {"year": yr}
                        for f, labels in fields.items():
                            row[f] = rv(s, *labels)
                        rows.append(row)
                    return rows

                income = parse_stmts("incomeStatementHistory","incomeStatementHistory",{
                    "revenue":  ["totalRevenue"],
                    "gross":    ["grossProfit"],
                    "ebit":     ["ebit"],
                    "net":      ["netIncome"],
                    "interest": ["interestExpense"],
                })
                balance = parse_stmts("balanceSheetHistory","balanceSheetStatements",{
                    "assets":  ["totalAssets"],
                    "liab":    ["totalLiab"],
                    "equity":  ["totalStockholderEquity"],
                    "cash":    ["cash"],
                    "st_debt": ["shortLongTermDebt","currentPortionOfLongTermDebt"],
                    "lt_debt": ["longTermDebt"],
                    "ca":      ["totalCurrentAssets"],
                    "cl":      ["totalCurrentLiabilities"],
                })
                cashflow = parse_stmts("cashflowStatementHistory","cashflowStatements",{
                    "ocf":   ["totalCashFromOperatingActivities"],
                    "capex": ["capitalExpenditures"],
                    "fcf":   ["freeCashflow"],
                })

                bs0  = balance[0]  if balance  else {}
                inc0 = income[0]   if income   else {}
                cf0  = cashflow[0] if cashflow else {}

                debt   = (bs0.get("st_debt") or 0) + (bs0.get("lt_debt") or 0)
                equity = bs0.get("equity")
                ca     = bs0.get("ca");  cl  = bs0.get("cl")
                rev    = inc0.get("revenue"); ni = inc0.get("net")
                ebit   = inc0.get("ebit");    iexp = inc0.get("interest")
                ocf    = cf0.get("ocf");      capx = cf0.get("capex")
                fcf    = cf0.get("fcf") or ((ocf or 0) + (capx or 0)) if ocf else None

                def fmti(r):
                    return {"year": r["year"],
                            "revenue":      _cr(r.get("revenue")),
                            "gross_profit": _cr(r.get("gross")),
                            "ebit":         _cr(r.get("ebit")),
                            "net_income":   _cr(r.get("net"))}

                def fmtb(r):
                    st = r.get("st_debt") or 0; lt = r.get("lt_debt") or 0
                    return {"year": r["year"],
                            "total_assets":     _cr(r.get("assets")),
                            "total_liabilities":_cr(r.get("liab")),
                            "equity":           _cr(r.get("equity")),
                            "cash":             _cr(r.get("cash")),
                            "total_debt":       _cr(st + lt),
                            "current_assets":   _cr(r.get("ca")),
                            "current_liab":     _cr(r.get("cl"))}

                def fmtc(r):
                    ocf_v  = r.get("ocf");  cap_v = r.get("capex")
                    fcf_v  = r.get("fcf") or ((ocf_v or 0) + (cap_v or 0)) if ocf_v else None
                    return {"year": r["year"],
                            "operating_cf":  _cr(ocf_v),
                            "free_cashflow": _cr(fcf_v),
                            "capex":         _cr(cap_v)}

                return {
                    "ticker": ticker, "source": "yahoo_finance",
                    "company":  ap.get("longName", ap.get("shortName", ticker)),
                    "sector":   ap.get("sector", ""),
                    "industry": ap.get("industry", ""),
                    "ratios": {
                        "pe":                _safe(rv(sd,"trailingPE") or rv(ks,"forwardPE")),
                        "pb":                _safe(rv(ks,"priceToBook")),
                        "de_ratio":          round(debt/equity,2) if equity and equity>0 else None,
                        "current_ratio":     round(ca/cl,2)       if ca and cl and cl>0  else None,
                        "net_margin_pct":    round(ni/rev*100,1)  if ni and rev           else None,
                        "roa_pct":           round(ni/bs0.get("assets")*100,1) if ni and bs0.get("assets") else None,
                        "interest_coverage": round(abs(ebit/iexp),1) if ebit and iexp and iexp!=0 else None,
                        "fcf_margin_pct":    round(fcf/rev*100,1) if fcf and rev else None,
                        "revenue_growth_pct":round((income[0]["revenue"]-income[1]["revenue"])/income[1]["revenue"]*100,1)
                                             if len(income)>=2 and income[0].get("revenue") and income[1].get("revenue") else None,
                        "roe_pct":           _safe((rv(fd,"returnOnEquity") or 0)*100, 1),
                    },
                    "income_statement": [fmti(r) for r in income],
                    "balance_sheet":    [fmtb(r) for r in balance],
                    "cash_flow":        [fmtc(r) for r in cashflow],
                }

            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    with _yahoo_lock: _yahoo_crumb["crumb"] = None
                    crumb, cookie = None, None  # reset so next iteration tries without crumb
                print(f"  [Yahoo] {ticker} {version}/{base}: HTTP {e.code}")
            except Exception as e:
                print(f"  [Yahoo] {ticker} {version}/{base}: {e}")

    return {"error": "All sources unavailable — Screener.in and Yahoo Finance both failed. Check internet connection.", "ticker": ticker}


# ──────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATORS
# ──────────────────────────────────────────────────────────────────────────────

def fetch_fundamentals(ticker):
    """Price + fundamentals. NSE India for live price, Screener for ratios."""
    result = {"ticker": ticker}

    # 1. Live price from NSE India
    nse = fetch_nse_quote(ticker)
    price = nse["price"] if nse else None
    name  = (nse.get("company") if nse else None) or ticker

    # 2. Price history (NSE history → Yahoo fallback)
    history = fetch_nse_history(ticker)
    if len(history) < 10:
        yp, yhist, yname, ype = fetch_yahoo_history(ticker)
        if not price:
            price = yp
        if not name or name == ticker:
            name = yname
        if yhist and len(yhist) > len(history):
            history = yhist

    result.update({
        "price":    price,
        "history":  history,
        "currency": "INR",
        "name":     name,
        "source":   "nse_official" if nse else "yahoo_finance",
    })
    if nse:
        result["change_pct"] = nse.get("change_pct")
        result["year_high"]  = nse.get("year_high")
        result["year_low"]   = nse.get("year_low")

    # 3. Fundamentals from Screener.in
    sc = fetch_screener(ticker)
    if sc:
        result["fundamentals"] = {
            "pe":  sc.get("pe"),   "pb":  sc.get("pb"),
            "roe": sc.get("roe"),  "rg":  sc.get("rg"),
            "pm":  sc.get("pm"),   "de":  sc.get("de"),
            "sector":   nse.get("sector","")   if nse else "",
            "industry": nse.get("industry","") if nse else "",
        }
    else:
        # Fallback: NSE P/E only
        result["fundamentals"] = {
            "pe":  nse.get("pe")  if nse else None,
            "pb":  None, "roe": None, "rg": None, "pm": None, "de": None,
            "sector":   nse.get("sector","")   if nse else "",
            "industry": nse.get("industry","") if nse else "",
        }

    return result


def fetch_balance_sheet(ticker):
    """Full balance sheet. Screener.in primary, Yahoo fallback."""
    print(f"\n── Balance Sheet: {ticker} ──")

    sc = fetch_screener(ticker)
    if sc:
        formatted = _screener_to_api(ticker, sc)
        if formatted and formatted.get("income_statement"):
            print(f"  {ticker}: balance sheet OK from Screener.in")
            return formatted

    print(f"  {ticker}: Screener failed, trying Yahoo Finance…")
    return _yahoo_balance_sheet(ticker)


# ──────────────────────────────────────────────────────────────────────────────
# LIVE MARKET NEWS — Google News RSS (no API key needed)
# ──────────────────────────────────────────────────────────────────────────────

import xml.etree.ElementTree as ET
import html as html_mod

NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=Indian+stock+market+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Nifty+50+Sensex+India+stocks&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=NSE+BSE+shares+India+investing&hl=en-IN&gl=IN&ceid=IN:en",
]

_news_cache = {"items": [], "fetched_at": 0}
NEWS_CACHE_TTL = 300  # refresh every 5 minutes

def fetch_market_news():
    global _news_cache
    now = time.time()
    if _news_cache["items"] and (now - _news_cache["fetched_at"]) < NEWS_CACHE_TTL:
        print("  [News] Serving from cache")
        return {"items": _news_cache["items"], "source": "google_news_rss", "cached": True}

    seen_titles = set()
    items = []

    for feed_url in NEWS_FEEDS:
        try:
            print(f"  [News] Fetching: {feed_url[:60]}...")
            raw, _ = _fetch(feed_url, headers={
                "Accept": "application/rss+xml,application/xml,text/xml,*/*",
                "Referer": "https://news.google.com/",
            }, timeout=12)

            root = ET.fromstring(raw)
            channel = root.find("channel")
            if channel is None:
                continue

            for item in channel.findall("item"):
                title_el   = item.find("title")
                link_el    = item.find("link")
                pubdate_el = item.find("pubDate")
                source_el  = item.find("source")

                title   = html_mod.unescape(title_el.text or "").strip() if title_el is not None else ""
                link    = (link_el.text or "").strip() if link_el is not None else ""
                pubdate = (pubdate_el.text or "").strip() if pubdate_el is not None else ""
                source  = (source_el.text or "Google News").strip() if source_el is not None else "Google News"

                # Clean up Google News title which appends " - Source Name"
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    if len(parts[1]) < 60:  # likely source suffix
                        title = parts[0].strip()
                        if not source or source == "Google News":
                            source = parts[1].strip()

                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)

                items.append({
                    "title":   title,
                    "link":    link,
                    "pubDate": pubdate,
                    "source":  source,
                })

                if len(items) >= 25:
                    break

        except Exception as e:
            print(f"  [News] Feed error: {e}")
            continue

        if len(items) >= 25:
            break

    if not items:
        print("  [News] All feeds failed — returning empty")
        return {"items": [], "source": "error", "error": "Could not fetch news"}

    print(f"  [News] Fetched {len(items)} articles")
    _news_cache = {"items": items, "fetched_at": now}
    return {"items": items, "source": "google_news_rss", "cached": False}



# ──────────────────────────────────────────────────────────────────────────────
# AI CHAT — Real-data augmented LLaMA via Groq
# ──────────────────────────────────────────────────────────────────────────────

# All NSE-listed tickers we know about (for fast regex matching in user messages)
_ALL_KNOWN_TICKERS = set(list(SECTOR_INDICES.get("NIFTY_BANK",[])) +
                          list(SECTOR_INDICES.get("NIFTY_IT",[])) +
                          list(SECTOR_INDICES.get("NIFTY_PHARMA",[])) +
                          list(SECTOR_INDICES.get("NIFTY_FMCG",[])) +
                          list(SECTOR_INDICES.get("NIFTY_AUTO",[])) +
                          list(SECTOR_INDICES.get("NIFTY_METAL",[])) +
                          list(SCREENER_SLUGS.keys()))

# Common company name → ticker mappings so users can type "Tata" or "Reliance"
COMPANY_NAME_MAP = {
    "tcs": "TCS", "tata consultancy": "TCS", "tata consultancy services": "TCS",
    "infosys": "INFY", "infy": "INFY",
    "wipro": "WIPRO",
    "hcl": "HCLTECH", "hcl tech": "HCLTECH", "hcl technologies": "HCLTECH",
    "tech mahindra": "TECHM",
    "reliance": "RELIANCE", "ril": "RELIANCE", "reliance industries": "RELIANCE",
    "hdfc bank": "HDFCBANK", "hdfc": "HDFCBANK",
    "icici bank": "ICICIBANK", "icici": "ICICIBANK",
    "sbi": "SBIN", "state bank": "SBIN", "state bank of india": "SBIN",
    "axis bank": "AXISBANK", "axis": "AXISBANK",
    "kotak": "KOTAKBANK", "kotak bank": "KOTAKBANK", "kotak mahindra": "KOTAKBANK",
    "bajaj finance": "BAJFINANCE", "bajaj fin": "BAJFINANCE",
    "bajaj finserv": "BAJAJFINSV",
    "maruti": "MARUTI", "maruti suzuki": "MARUTI",
    "tata motors": "TATAMOTORS",
    "mahindra": "M&M", "m&m": "M&M",
    "hero": "HEROMOTOCO", "hero motocorp": "HEROMOTOCO",
    "bajaj auto": "BAJAJ-AUTO",
    "eicher": "EICHERMOT", "royal enfield": "EICHERMOT",
    "sun pharma": "SUNPHARMA", "sun pharmaceutical": "SUNPHARMA",
    "dr reddy": "DRREDDY", "dr reddys": "DRREDDY", "dr. reddy": "DRREDDY",
    "cipla": "CIPLA",
    "divi": "DIVISLAB", "divis": "DIVISLAB", "divis labs": "DIVISLAB",
    "apollo": "APOLLOHOSP", "apollo hospitals": "APOLLOHOSP",
    "asian paints": "ASIANPAINT",
    "hindustan unilever": "HINDUNILVR", "hul": "HINDUNILVR",
    "itc": "ITC",
    "nestle": "NESTLEIND", "nestle india": "NESTLEIND",
    "titan": "TITAN",
    "larsen": "LT", "l&t": "LT", "larsen and toubro": "LT",
    "ongc": "ONGC",
    "ntpc": "NTPC",
    "coal india": "COALINDIA",
    "tata steel": "TATASTEEL",
    "jsw steel": "JSWSTEEL",
    "adani": "ADANIENT", "adani enterprises": "ADANIENT",
    "zomato": "ZOMATO",
    "irctc": "IRCTC",
    "dmart": "DMART", "avenue supermarts": "DMART",
    "power grid": "POWERGRID",
    "bpcl": "BPCL", "bharat petroleum": "BPCL",
    "ioc": "IOC", "indian oil": "IOC",
}

def extract_tickers_from_message(text):
    """Smartly extract stock tickers/company names from a user message."""
    found = set()
    text_lower = text.lower()

    # 1. Direct ticker matches (UPPERCASE words 2-12 chars)
    for word in re.findall(r"\b([A-Z][A-Z0-9&.-]{1,11})\b", text):
        if word in _ALL_KNOWN_TICKERS:
            found.add(word)

    # 2. Company name → ticker mapping
    for name, ticker in COMPANY_NAME_MAP.items():
        if name in text_lower:
            found.add(ticker)

    # 3. Common patterns like "TCS shares", "buy Infosys", "HDFC stock"
    stock_keywords = re.findall(
        r"\b(\w+(?:\s+\w+)?)\s+(?:shares?|stock|scrip|equity|NSE|BSE)\b",
        text_lower)
    for phrase in stock_keywords:
        phrase = phrase.strip()
        if phrase in COMPANY_NAME_MAP:
            found.add(COMPANY_NAME_MAP[phrase])
        # Try as direct ticker
        upper = phrase.upper()
        if upper in _ALL_KNOWN_TICKERS:
            found.add(upper)

    return list(found)[:4]  # cap at 4 stocks per query


def build_stock_context(tickers):
    """Fetch real data for tickers and build a structured context string for LLaMA."""
    if not tickers:
        return "", {}

    sections = []
    raw_data = {}

    for ticker in tickers:
        print(f"  [AI-Chat] Fetching data for {ticker}…")
        fund = fetch_fundamentals(ticker)
        sc   = fetch_screener(ticker)
        raw_data[ticker] = {"fundamentals": fund, "screener": sc}

        price    = fund.get("price")
        chg      = fund.get("change_pct")
        name     = fund.get("name", ticker)
        f        = fund.get("fundamentals", {})
        yh       = fund.get("year_high")
        yl       = fund.get("year_low")

        # Price position within 52W range
        pos_52w = ""
        if price and yh and yl and yh > yl:
            pct = round((price - yl) / (yh - yl) * 100, 1)
            pos_52w = f"(at {pct}% of 52W range)"

        # Build history summary (6M trend)
        hist = fund.get("history", [])
        trend_str = ""
        if len(hist) >= 60:
            price_6m_ago = hist[max(0, len(hist)-125)]["price"]
            if price_6m_ago and price:
                g6m = round((price - price_6m_ago) / price_6m_ago * 100, 1)
                trend_str = f"6M return: {'+' if g6m>=0 else ''}{g6m}%"

        # Screener financial tables (last 3 years)
        income_rows = ""
        if sc:
            pl  = sc.get("income_statement", {})
            yrs = pl.get("years", [])
            rev_row = _get_row(pl, "Sales", "Revenue", "Net Sales") or []
            ni_row  = _get_row(pl, "Net Profit", "Profit after tax", "PAT") or []
            op_row  = _get_row(pl, "Operating Profit", "EBITDA") or []

            rows_data = []
            for i, yr in enumerate(yrs[:4]):
                rev = f"₹{rev_row[i]/100:.0f}K Cr" if i < len(rev_row) and rev_row[i] else "N/A"
                ni  = f"₹{ni_row[i]/100:.0f}K Cr" if i < len(ni_row) and ni_row[i] else "N/A"
                op  = f"₹{op_row[i]/100:.0f}K Cr" if i < len(op_row) and op_row[i] else "N/A"
                rows_data.append(f"  {yr}: Revenue {rev}, Op.Profit {op}, Net Profit {ni}")
            if rows_data:
                income_rows = "Financial History (Screener.in):\n" + "\n".join(rows_data)

        section = f"""
━━━ {name} ({ticker}) ━━━
Live Price:    ₹{price:,.2f} {'('+str(chg)+'% today)' if chg else ''} {pos_52w}
52-Week Range: ₹{yl} – ₹{yh}
{trend_str}

Valuation:
  P/E Ratio:   {f.get('pe') or 'N/A'}
  P/B Ratio:   {f.get('pb') or 'N/A'}

Profitability:
  ROE:         {str(f.get('roe'))+'%' if f.get('roe') else 'N/A'}
  Net Margin:  {str(f.get('pm'))+'%' if f.get('pm') else 'N/A'}

Financial Health:
  D/E Ratio:   {f.get('de') or 'N/A'}
  Revenue Growth (YoY): {str(f.get('rg'))+'%' if f.get('rg') else 'N/A'}

{income_rows}
Sector: {f.get('sector') or 'N/A'} | Industry: {f.get('industry') or 'N/A'}
Data Sources: NSE India (live price) + Screener.in (fundamentals)
"""
        sections.append(section.strip())

    context = "\n\n".join(sections)
    return context, raw_data


def _get_row(table, *keys):
    """Get a row from a parsed financial table by trying multiple key names."""
    if not table or not isinstance(table, dict):
        return None
    rows = table.get("rows", {})
    if not rows:
        return None
    for key in keys:
        for rk, rv in rows.items():
            if key.lower() in rk.lower():
                return rv
    return None


def handle_ai_chat(body_bytes):
    """Main handler: extract tickers → fetch data → inject into LLaMA prompt → return response."""
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return {"error": "Invalid JSON body"}, 400

    messages      = payload.get("messages", [])
    groq_api_key  = payload.get("groq_api_key", "")
    if not groq_api_key:
        return {"error": "groq_api_key missing"}, 400
    if not messages:
        return {"error": "messages missing"}, 400

    # Extract latest user message
    user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_msg = m.get("content", "")
            break

    # Step 1: extract tickers from user message
    tickers = extract_tickers_from_message(user_msg)
    print(f"  [AI-Chat] Tickers detected: {tickers}")

    # Step 2: fetch real data
    stock_context, raw_data = build_stock_context(tickers)

    # Step 3: build system prompt with injected real data
    if stock_context:
        system_prompt = f"""You are NeStiQ AI Advisor, an expert in Indian stock markets (NSE/BSE).

REAL-TIME MARKET DATA has been fetched for you RIGHT NOW from NSE India and Screener.in:

{stock_context}

INSTRUCTIONS:
- Use the EXACT numbers above in your analysis. Do not guess or hallucinate figures.
- When you quote P/E, price, ROE or any metric — it comes from the live data above.
- If data shows N/A for a metric, say it's not available rather than guessing.
- Structure your response: Price Analysis → Valuation → Financials → Verdict
- Be precise, use numbers, and give a clear investment perspective.
- Keep response to 4-6 paragraphs. Format with <strong> for key terms."""
    else:
        system_prompt = """You are NeStiQ AI Advisor, an expert in Indian stock markets (NSE/BSE).
You help users understand stocks, investment strategies, and financial concepts relevant to India.
Key focus areas: Nifty 50 stocks, fundamentals (P/E, P/B, ROE, D/E), technical analysis basics,
SIP vs lump sum, sectoral trends, and risk management.
Format responses with clear sections using <strong> for emphasis. Keep responses concise (3-5 paragraphs max).
Do not add any disclaimer at the end of your response."""

    # Step 4: call Groq LLaMA
    groq_payload = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 900,
        "messages": [
            {"role": "system", "content": system_prompt},
            *[{"role": m["role"], "content": m["content"]} for m in messages]
        ]
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=groq_payload,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {groq_api_key}",
            }
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode("utf-8"))

        reply = resp["choices"][0]["message"]["content"]
        return {
            "reply":        reply,
            "tickers_used": tickers,
            "data_fetched": bool(stock_context),
            "sources":      ["NSE India", "Screener.in"] if stock_context else [],
        }, 200

    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        try:   err_json = json.loads(err_body)
        except: err_json = {"raw": err_body}
        print(f"  [AI-Chat] Groq error {e.code}: {err_body[:200]}")
        return {"error": f"Groq API error {e.code}", "detail": err_json}, 502

    except Exception as e:
        print(f"  [AI-Chat] Error: {e}")
        return {"error": str(e)}, 500


# ──────────────────────────────────────────────────────────────────────────────
# HTTP SERVER
# ──────────────────────────────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200); self.send_cors(); self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        qs     = parse_qs(parsed.query)
        path   = parsed.path

        if path == "/price":
            raw = qs.get("tickers",[""])[0]
            if not raw: return self.reply(400, {"error":"Missing tickers"})
            tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
            print(f"\n── /price {tickers} ──")
            self.reply(200, {"results": {t: fetch_fundamentals(t) for t in tickers}})

        elif path == "/balance-sheet":
            raw = qs.get("tickers",[""])[0]
            if not raw: return self.reply(400, {"error":"Missing tickers"})
            tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
            print(f"\n── /balance-sheet {tickers} ──")
            self.reply(200, {"results": {t: fetch_balance_sheet(t) for t in tickers}})

        elif path == "/sector-index":
            idx = qs.get("index",[""])[0].strip().upper().replace("-","_")
            if not idx or idx not in SECTOR_INDICES:
                return self.reply(404, {"error":f"Unknown index '{idx}'",
                                        "available":list(SECTOR_INDICES.keys())})
            stocks = SECTOR_INDICES[idx]
            print(f"\n── /sector-index {idx} ({len(stocks)} stocks) ──")
            self.reply(200, {"index":idx,"constituents":stocks,
                             "results":{t: fetch_fundamentals(t) for t in stocks}})

        elif path == "/debug-screener":
            # Debug endpoint: shows raw Screener HTML snippet + parsed ratios
            # Usage: http://localhost:5000/debug-screener?ticker=CIPLA
            ticker = qs.get("ticker",[""])[0].strip().upper()
            if not ticker:
                return self.reply(400, {"error":"Missing ticker param"})
            slug = SCREENER_SLUGS.get(ticker, ticker.lower())
            debug = {"ticker": ticker, "slug": slug, "attempts": []}
            for suffix in ["consolidated/", ""]:
                url = f"https://www.screener.in/company/{slug}/{suffix}"
                try:
                    text, _ = _fetch(url, headers={"Referer":"https://www.screener.in/","Accept":"text/html,*/*"}, timeout=22)
                    # Find PE context
                    pe_idx = text.lower().find("p/e")
                    roe_idx = text.lower().find("return on equity")
                    debug["attempts"].append({
                        "url": url,
                        "length": len(text),
                        "pe_context":  text[max(0,pe_idx-100):pe_idx+300] if pe_idx>=0 else "NOT FOUND",
                        "roe_context": text[max(0,roe_idx-100):roe_idx+300] if roe_idx>=0 else "NOT FOUND",
                        "parsed": _parse_screener(text, ticker),
                    })
                    break
                except Exception as e:
                    debug["attempts"].append({"url": url, "error": str(e)})
            self.reply(200, debug)

        elif path == "/stock-context":
            # Frontend calls this: ?tickers=TCS,INFY  OR  ?q=user+message+text
            # Returns structured real-data context string + raw data for each ticker
            raw_q  = qs.get("q",[""])[0].strip()
            raw_t  = qs.get("tickers",[""])[0].strip()

            if raw_q:
                tickers = extract_tickers_from_message(raw_q)
            elif raw_t:
                tickers = [t.strip().upper() for t in raw_t.split(",") if t.strip()][:4]
            else:
                return self.reply(400, {"error": "Provide ?q=message or ?tickers=TCS,INFY"})

            print(f"\n── /stock-context  tickers={tickers} ──")
            if not tickers:
                return self.reply(200, {"tickers": [], "context": "", "data": {}})

            context_str, raw_data = build_stock_context(tickers)
            # Simplify raw_data for JSON (remove history array to keep response small)
            slim = {}
            for t, d in raw_data.items():
                f = d.get("fundamentals", {})
                slim[t] = {
                    "name":       f.get("fundamentals",{}) and f.get("name", t),
                    "price":      f.get("price"),
                    "change_pct": f.get("change_pct"),
                    "year_high":  f.get("year_high"),
                    "year_low":   f.get("year_low"),
                    "pe":         (f.get("fundamentals") or {}).get("pe"),
                    "pb":         (f.get("fundamentals") or {}).get("pb"),
                    "roe":        (f.get("fundamentals") or {}).get("roe"),
                    "de":         (f.get("fundamentals") or {}).get("de"),
                    "pm":         (f.get("fundamentals") or {}).get("pm"),
                    "rg":         (f.get("fundamentals") or {}).get("rg"),
                }
            self.reply(200, {
                "tickers": tickers,
                "context": context_str,
                "data":    slim,
                "sources": ["NSE India", "Screener.in"],
            })

        elif path == "/health":
            self.reply(200, {
                "status":          "ok",
                "port":            PORT,
                "nse_session":     bool(_nse_session.get("cookies")),
                "screener_cached": len(_screener_cache),
                "sector_indices":  list(SECTOR_INDICES.keys()),
                "data_sources":    ["NSE India (official)","Screener.in","Yahoo Finance (chart fallback)"],
                "endpoints": {
                    "GET /stock-context?q=message": "Extract tickers + fetch real data → context string",
                    "GET /stock-context?tickers=TCS,INFY": "Fetch data for specific tickers",
                    "GET /price?tickers=TCS": "Price + fundamentals",
                    "GET /news": "Live market news",
                }
            })

        elif path == "/news":
            print("\n── /news ──")
            self.reply(200, fetch_market_news())

        else:
            self.reply(404, {"error":"Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        if path == "/ai-chat":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length) if length > 0 else b"{}"
            print(f"\n── /ai-chat (POST) {len(body)} bytes ──")
            result, code = handle_ai_chat(body)
            self.reply(code, result)
        else:
            self.reply(404, {"error": "Not found"})

    def reply(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_cors()
        self.end_headers()
        self.wfile.write(body)


# ──────────────────────────────────────────────────────────────────────────────
# STARTUP
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    SEP = "=" * 64

    def _prewarm():
        time.sleep(1)
        print("  Warming NSE India session…")
        _get_nse_cookies()
        print("  Ready — NSE India session active")

    threading.Thread(target=_prewarm, daemon=True).start()

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"\n{SEP}")
        print(f"  NeStiQ Data Server  -  port {PORT}")
        print(f"")
        print(f"  DATA SOURCES:")
        print(f"    1. NSE India (nseindia.com)  - official government exchange")
        print(f"       Live price, P/E, 52W range - no API key needed")
        print(f"    2. Screener.in               - best free Indian stock fundamentals")
        print(f"       Balance sheet, ROE, D/E, FCF, 5-year financials")
        print(f"    3. Yahoo Finance             - chart history fallback only")
        print(f"")
        print(f"  ENDPOINTS:")
        print(f"    /price?tickers=TCS,INFY         -> Price + fundamentals")
        print(f"    /balance-sheet?tickers=TCS,INFY -> Full balance sheet analysis")
        print(f"    /sector-index?index=NIFTY_BANK  -> All sector index stocks")
        print(f"    /news                           -> Live Google News RSS (25 articles)")
        print(f"    /health                         -> Server status")
        print(f"    POST /ai-chat                   -> Real-data augmented LLaMA (NEW!)")
        print(f"")
        print(f"  AI CHAT FLOW:")
        print(f"    User message → extract tickers → fetch NSE+Screener data")
        print(f"    → inject real numbers into LLaMA prompt → precise AI response")
        print(f"")
        print(f"  SECTOR INDICES:")
        for k, v in SECTOR_INDICES.items():
            print(f"    {k:<22} ({len(v)} stocks)")
        print(f"")
        print(f"  Open nestiq.html in browser  |  Stop: Ctrl+C")
        print(f"{SEP}\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped.")

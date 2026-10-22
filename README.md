# NeStiQ — Indian Stock Market Intelligence & Analysis Platform

> **"Smarter Insights. Stronger Trades."**  
> *Explainable AI Financial Intelligence for Indian Equities (NSE/BSE)*

---

## 🌟 Executive Overview

**NeStiQ** is a comprehensive, explainable AI financial intelligence platform tailored specifically for the Indian equity markets. Moving beyond black-box predictions, NeStiQ pairs **deterministic financial models** and **probabilistic machine learning** with causal explanations ("WHY?"), giving both retail investors and institutional analysts actionable, transparent market clarity.

---

## 🏛️ Dual Dashboard Architecture

NeStiQ features a seamless dual-mode switch directly accessible from the sidebar:

1. **🌱 NeStiQ Investor (Retail Dashboard)**
   - Clear, jargon-free investment intelligence.
   - Green / Yellow / Red visual risk indicators.
   - Plain-language AI summaries, key financial moats, and SIP compounding calculators.
   - Direct Academy learning integration.

2. **⚡ NeStiQ Intelligence (Quantitative & Analyst Dashboard)**
   - Deep-dive balance sheet breakdowns, DuPont ROE decomposition, and multi-year ratio histories.
   - Herfindahl-Hirschman Index (HHI) concentration risk analytics.
   - Machine learning out-of-sample confusion matrices, backtest strategy returns, and alpha metrics.
   - Macroeconomic sensitivity transmission channels.

---

## 🚀 Signature Capabilities

### 1. 🧬 Stock DNA (8-Dimension Financial Fingerprint)
Evaluates any Indian stock across 8 core dimensions on an interactive multi-axis canvas:
- **Quality** (Capital compounding power)
- **Growth** (Top-line revenue expansion)
- **Valuation** (P/E & P/B multiple safety)
- **Profitability** (EBITDA & Net margins)
- **Financial Strength** (Solvency & D/E health)
- **Momentum** (1Y price trajectory confirmation)
- **Cash Flow** (Free cash flow generation)
- **Risk Stability** (Volatility & debt insulation)

*Supports side-by-side comparative DNA benchmarking (e.g., TCS vs INFY).*

### 2. 🛡️ NeStiQ Risk Radar (Early Warning System)
Monitors 5 empirical pillars with measurable causal reasoning and down-side alerts:
- **Valuation Multiple Risk**
- **Debt & Solvency Risk**
- **Profitability Degradation Risk**
- **Momentum & Trend Risk**
- **Sentiment & Macro Headwind Risk**

### 3. ⚡ AI Stock Direction & Model Lab
- **Scikit-Learn Machine Learning**: Uses chronological time-series splitting (75% train / 25% test with strictly zero look-ahead bias).
- **Probabilistic Predictions**: Forecasts 5-day and 20-day directional probabilities (`Bullish %`, `Neutral %`, `Bearish %`).
- **Feature Attribution**: Lists top positive and negative contributing fundamental & technical factors.
- **Model Lab**: Full out-of-sample test accuracy, Macro F1-score, strategy backtest performance, alpha vs benchmark, and 3x3 confusion matrix.

### 4. 🩺 Portfolio Doctor & What-If Simulator
- **Health Scorecard**: Diagnoses portfolio diversification, quality moat, downside safety, valuation multiple risk, and cash flow stability.
- **Concentration Tracking**: Real-time HHI concentration metrics and sector exposure alerts.
- **What-If Sandbox**: Simulate adding or trimming positions to preview the exact numerical impact on portfolio health and diversification **BEFORE** executing live orders.

### 5. 🔬 Scenario Lab (Macroeconomic Sensitivity Engine)
Simulates macroeconomic shocks on Indian equities:
- **💵 Rupee (INR) Depreciation (-5%)** (Exporters IT/Pharma vs importers)
- **🏛️ RBI Repo Rate Hike (+50 bps)** (Banking NIM expansion vs borrowing costs)
- **🛢️ Crude Oil Surge (+$15/bbl)** (Upstream exploration vs FMCG/paint input margins)
- **💻 Global Tech Slowdown**
- **🏦 Banking Credit Growth Pause**

### 6. 🤖 Multilingual AI Copilot
- **8 Indian Languages**: English, தமிழ் (Tamil), हिन्दी (Hindi), తెలుగు (Telugu), മലയാളം (Malayalam), ಕನ್ನಡ (Kannada), বাংলা (Bengali), and मराठी (Marathi).
- **Voice Input**: Web Speech Recognition microphone integration.
- **Audio TTS Response**: Built-in speech synthesis.
- **Secure Backend Proxy**: All requests route through `POST /ai-chat`. Groq API key is stored securely in backend `.env` with zero frontend exposure and an automatic fallback to NeStiQ's deterministic Reasoner.

### 7. 🧮 100-Point Deterministic Scoring Formula
Every stock displays an interactive **[Show Calculation]** button detailing the exact points awarded:
- **P/E Ratio (Margin of Safety)**: Up to 35 pts (Highest Weight)
- **ROE (Capital Efficiency)**: Up to 25 pts
- **Price Uptrend (1Y Trajectory)**: Up to 20 pts
- **P/B Ratio (Tangible Asset Value)**: Up to 10 pts
- **Profit Margin**: Up to 6 pts
- **Debt Penalty**: Deducts up to -12 pts for high D/E leverage

---

## 📁 Repository Structure

```text
nestiq-srock-analyser-main/
│
├── nestiq_v10.html             # Full-featured Single-Page Web Application
├── server_v4.py                # Python Async/HTTP Backend & API Gateway
├── ml_engine.py                # Scikit-Learn ML Model & Financial Intelligence Engine
├── nestiq_logo.png             # Official NeStiQ Brand Logo
├── .env                        # Local Environment Configuration (API Keys)
├── .env.example                # Template for Environment Configuration
├── .gitignore                  # Git Ignore Configuration
├── README.md                   # This Documentation Manual
└── NeStiQ_v10_Complete.zip     # Complete Downloadable Package
```

---

## ⚡ Quick Start Guide

### 1. Requirements
- Python 3.9 or higher (tested on Python 3.10 – 3.14)
- Google Chrome, Microsoft Edge, or any modern web browser

### 2. Dependencies
Install the required analytical and financial libraries:
```bash
pip install numpy pandas scikit-learn yfinance requests
```

### 3. API Key Setup (Optional)
If you wish to use Groq LLaMA 3.3 for the AI Copilot:
1. Open `.env` (or copy `.env.example` to `.env`):
   ```ini
   GROQ_API_KEY=your_actual_groq_api_key_here
   PORT=5000
   ```
2. *Note: If no key is provided, NeStiQ automatically falls back to its built-in Multilingual Quantitative Reasoner. It will never fail or show error alerts.*

### 4. Running the Platform
1. **Start the Backend Server**:
   ```bash
   python server_v4.py
   ```
   *The server starts on `http://localhost:5000` with live NSE, Screener.in, and ML endpoints active.*

2. **Open the Dashboard**:
   - Double-click `nestiq_v10.html` to open it in your web browser.
   - Alternatively, visit `http://localhost:5000/` or serve it with any local static web server.

---

## 🔒 Security & Privacy Invariant
- **Zero Frontend API Keys**: No API keys are embedded in `nestiq_v10.html` or client scripts.
- **Local Data Processing**: Portfolio positions and simulations remain in your browser's private local storage.

---

## 📜 License & Disclaimers
*NeStiQ is an educational and analytical decision-support tool. It provides quantitative and probabilistic market intelligence, not personalized financial advice. Users should conduct their own research before making investment decisions.*

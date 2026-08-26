# 📈 StockStream — Real-Time AI Investment Platform

A production-grade real-time stock market data pipeline with an autonomous 
AI Investment Advisor powered by Anthropic Claude.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![AWS](https://img.shields.io/badge/AWS-Kinesis%20%7C%20Lambda%20%7C%20DynamoDB%20%7C%20S3-orange)
![Claude](https://img.shields.io/badge/Anthropic-Claude%20API-red)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-pink)

---

## 🎯 Problem

Stock market data is publicly available but:
- **Too much noise** — prices change every second, hard to analyse manually
- **No intelligence** — raw prices alone don't tell you whether to buy or sell
- **Scattered tools** — streaming, storage, analysis, and AI exist separately
- **No real-time answers** — you can't ask plain English questions and get 
  data-backed investment analysis instantly

Most investment platforms either give you raw data with no AI, or AI with no 
real data. StockStream combines both.

---

## ✅ Solution

StockStream is an end-to-end real-time investment intelligence platform that:

1. **Streams real live stock prices** from Yahoo Finance every 120 seconds
2. **Processes them through AWS** — Kinesis → Lambda → DynamoDB + S3
3. **Runs technical analysis** — RSI, MACD, Moving Averages, Bollinger Bands
4. **Answers any investment question** using an autonomous Claude AI Agent 
   that fetches live data and chains multiple analytical tools together
5. **Displays everything** on a live Streamlit dashboard with interactive charts

---

## 🏗️ Architecture

```
Yahoo Finance API (real live prices)
         ↓
Python Producer (every 120 seconds)
         ↓
AWS Kinesis Data Stream
         ↓
AWS Lambda (serverless consumer)
         ↓
    ┌────┴────────────┐
    ↓                 ↓
Amazon DynamoDB    Amazon S3
(latest prices)    (full history)
    ↓                 ↓
Technical Analysis Engine
(RSI · MACD · Moving Averages · Bollinger Bands)
         ↓
Autonomous AI Investment Advisor
(Anthropic Claude + Tool Calling)
         ↓
Streamlit Dashboard
(Live charts · Price cards · AI Chat)
```

---

## 🚀 Features

### Real-Time Data Pipeline
- Live stock prices from Yahoo Finance — AAPL, GOOGL, MSFT, AMZN, TSLA
- AWS Kinesis streams data in real time
- Lambda processes each batch serverlessly — no servers to manage
- DynamoDB stores latest price per stock for instant dashboard reads
- S3 stores complete historical data partitioned by date and hour
- Athena enables SQL queries directly on S3 historical data

### Technical Analysis Engine
- **Moving Averages** — MA7, MA20, MA50 for short, medium and long term trends
- **RSI** — 14-period Relative Strength Index, overbought >70, oversold <30
- **MACD** — EMA12 minus EMA26 with signal line crossover detection
- **Bollinger Bands** — volatility bands for mean reversion signals
- **Composite signal** — combines all indicators into BUY / HOLD / SELL with confidence %

### Autonomous AI Investment Advisor
The AI agent uses Anthropic Claude tool calling — it autonomously decides 
which tools to call, chains multiple steps, and answers any investment question:

- `get_live_price` — fetches current price from DynamoDB
- `get_technical_analysis` — runs full RSI, MACD, MA analysis
- `compare_all_stocks` — ranks all 5 stocks by investment potential
- `get_price_history` — retrieves historical trend data

**Short term questions:** "Should I buy TSLA this week?"
**Long term questions:** "Which stock is best to hold for 6 months?"
**Comparison questions:** "Rank all 5 stocks from best to worst right now"

### Live Dashboard
- 5 real-time price cards with % change and REAL/SIM badge
- Interactive price chart with MA lines overlaid
- RSI chart with overbought and oversold zones highlighted
- Volume bar chart with colour-coded price direction
- AI chat sidebar with quick question buttons
- Stock selector to switch between all 5 stocks

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Data source | Yahoo Finance API (yfinance) |
| Streaming | AWS Kinesis Data Streams |
| Processing | AWS Lambda (serverless) |
| Real-time DB | Amazon DynamoDB |
| Historical storage | Amazon S3 |
| SQL analytics | Amazon Athena |
| Technical analysis | Python · pandas · numpy |
| AI Agent | Anthropic Claude API (tool calling) |
| Dashboard | Streamlit · Plotly |
| Cloud SDK | boto3 |
| Security | AWS IAM · environment variables |

---

## 📁 Project Structure

```
stockstream/
├── producer/
│   ├── simulator.py          # Simulated stock data producer
│   └── real_producer.py      # Real Yahoo Finance data producer
├── consumer/
│   └── lambda_function.py    # AWS Lambda consumer
├── analyser/
│   └── technical.py          # RSI, MACD, MA, Bollinger Bands engine
├── ai/
│   └── advisor.py            # Claude AI Investment Advisor
├── dashboard/
│   └── app.py                # Streamlit dashboard
├── tests/
│   ├── test_setup.py         # AWS connection tests
│   ├── test_producer.py      # Producer unit tests
│   ├── test_lambda.py        # Lambda consumer tests
│   └── test_technical.py     # Technical analysis tests
├── .env                      # Environment variables (not committed)
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.12+
- AWS account with IAM user configured
- Anthropic API key

### 1. Clone the repository
```bash
git clone https://github.com/Prachi2822-del/stockstream
cd stockstream
```

### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the project root:
```
AWS_ACCESS_KEY_ID=your_key_here
AWS_SECRET_ACCESS_KEY=your_secret_here
AWS_DEFAULT_REGION=ap-southeast-2
KINESIS_STREAM_NAME=stockstream-prices
DYNAMODB_TABLE=stock_prices
S3_BUCKET=your-bucket-name
ANTHROPIC_API_KEY=your_anthropic_key_here
```

### 5. Set up AWS services
```bash
# Create Kinesis stream
aws kinesis create-stream --stream-name stockstream-prices --shard-count 1

# Create DynamoDB table
aws dynamodb create-table \
  --table-name stock_prices \
  --attribute-definitions \
    AttributeName=symbol,AttributeType=S \
    AttributeName=timestamp,AttributeType=S \
  --key-schema \
    AttributeName=symbol,KeyType=HASH \
    AttributeName=timestamp,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST
```

### 6. Test AWS connections
```bash
python tests/test_setup.py
```

---

## ▶️ Running the Platform

### Terminal 1 — Start real data producer
```bash
python producer/real_producer.py
```

### Terminal 2 — Start dashboard
```bash
streamlit run dashboard/app.py
```

Open `http://localhost:8501` in your browser.

### Run AI advisor in terminal (optional)
```bash
python ai/advisor.py
```

---

## 💬 Example AI Advisor Questions

```
"Which stock should I buy right now for short term?"
"Is TSLA a good buy today?"
"Which stock is best to hold for 6 months?"
"Rank all 5 stocks from best to worst"
"Which stock has the highest RSI right now?"
"Give me a full market overview"
"What is the riskiest stock right now?"
"Should I buy MSFT or AAPL?"
```

---

## 📊 Technical Indicators Explained

### RSI (Relative Strength Index)
Measures buying and selling pressure on a 0-100 scale.
- Above 70 = overbought, price likely to fall
- Below 30 = oversold, price likely to bounce
- 30-70 = neutral zone

### MACD (Moving Average Convergence Divergence)
Measures momentum by comparing EMA12 and EMA26.
- MACD crosses above signal line = bullish momentum building
- MACD crosses below signal line = bearish momentum building

### Moving Averages
Smooths price noise to show trend direction.
- Price above MA7 and MA20 = short term uptrend
- MA7 above MA50 = long term uptrend (golden cross)
- MA7 below MA50 = long term downtrend (death cross)

---

## ⚠️ Disclaimer

This platform provides **technical analysis only** and is **NOT financial advice**. 
Always consult a licensed financial advisor before making any investment decisions. 
Past performance does not guarantee future results.

---

## 👩‍💻 Author

**Prachi Vharkal**
Master of Data Science with AI — University of Sydney (2026)
Open to Data Engineering · AI Engineering · Cloud Engineering roles across Australia

- GitHub: [Prachi2822-del](https://github.com/Prachi2822-del)
- LinkedIn: [prachivharkal](https://linkedin.com/in/prachivharkal)

---

## 📄 License

MIT License — free to use and modify with attribution.

"""
advisor.py
AI Investment Advisor powered by Anthropic Claude.
Uses tool calling to fetch real live data before answering.

The agent autonomously decides which tools to call based on
the user's question, chains them together, and gives a 
complete investment recommendation with real numbers
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import boto3
import anthropic
from dotenv import load_dotenv
from decimal import Decimal
from analyser.technical import analyse_stock, compare_all_stocks

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2"))

STOCKS = ["AAPL", "GOOGLE", "MSFT", "AMZN", "TSLA"]

# Tool definations

TOOLS = [
    {
        "name": "get_live_price",
        "description": (
            "Get the current live price and recent change for a specific stock. "
            "Use this when asked about current price of any stock."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol e.g. AAPL, GOOGLE, MSFT, AMZN, TSLA"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_technical_analysis",
        "description": (
            "Get full technical analysis for a stock including RSI, MACD, "
            "moving averages, and buy/sell signals for short term and long term. "
            "Use this when asked for investment advice on a specific stock."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol e.g. AAPL, GOOGLE, MSFT, AMZN, TSLA"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "compare_stocks",
        "description": (
            "Compare all 5 stocks and rank them by investment potential. "
            "Use this when asked which stock is best to buy, "
            "or for a market overview."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "timeframe": {
                    "type": "string",
                    "enum": ["short_term", "long_term", "both"],
                    "description": "Investment timeframe to focus on"
                }
            },
            "required": ["timeframe"]
        }
    },
    {
        "name": "get_price_history",
        "description": (
            "Get recent price history for a stock to analyse trends. "
            "Use this when asked about price trends or historical performance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of recent price records to fetch default 20"
                }
            },
            "required": ["symbol"]
        }
    }
]

# Tool Executors
def decimal_to_float(obj):
    """ Convert Decimal to float for JSON serialisation. """
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")

def execute_get_live_price(symbol: str) -> dict:
    """ Fetch latest price from DynamoDB. """
    try:
        symbol = symbol.upper()
        result = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.key("symbol").eq(symbol),
            ScanIndexForward=False,
            Limit=1
        )
        items = result.get("Items", []),
        if not items:
            return {"error": f"No data found for {symbol}"}

        item = items[0]
        return {
            "symbol":       item["symbol"],
            "price":        float(item["price"]),
            "price_change": float(item.get("price_change", 0)),
            "pct_change":   float(item.get("pct_change", 0)),
            "timestamp":    str(item["timestamp"])
        }
    except Exception as e:
        return {"error": str(e)}

def execute_get_technical_analysis(symbol: str) -> dict:
    """ Run technical analysis on a stock. """
    try:
        result = analyse_stock(symbol.upper())
        # Remove the df object - not JSON serialisable
        result.pop("df", None)
        return result
    except Exception as e:
        return {"error": str(e)}

def execute_compare_all_stocks(timeframe: str) -> dict:
    """ Compare a;; stocks and return ranked list. """
    try:
        results = compare_all_stocks()
        # Remove df objects
        for r in results:
            r.pop("df", None)

        if timeframe =="short_term":
            results.sort(
                key=lambda x: (
                    [" STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]
                    .index(x.get("short_term", "HOLD"))
                    if x.get("short_term") in
                    [" STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]
                    else 2
                )
            )
        elif timeframe == "long_term":
            results.sort(
                key=lambda x: (
                    [" STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]
                    .index(x.get("long_term", "HOLD"))
                    if x.get("long_term") in
                    [" STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]
                    else 2
                )
            )

        return {"stocks": results, "timeframe": timeframe}
    except Exception as e:
        return {"error": str(e)} 

def execute_get_price_history(symbol: str, limit: int= 20) -> dict:
    """ Get recent history. """
    try:
        result = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.key("symbol").eq(symbol.upper()),
            ScanIndexForward=False,
            Limit=limit
        )
        items = result.get("Items", [])
        prices =[
            {
                "price":      float(i["price"]),
                "pct_change": float(i.get("pct_change", 0)),
                "timestamp":  str(i["timestamp"]) 
            }
            for i in reversed(items)
        ]
        return {"symbol": symbol, "history": prices, "count": len(prices)}
    except Exception as e:
        return{ "error": str(e)}

def execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "get_live_price":
        result = execute_get_live_price(tool_input["symbol"])
    elif tool_name == "get_technical_analysis":
        result = execute_get_technical_analysis(tool_input["symbol"])
    elif tool_name == "compare_stocks":
        result = execute_compare_all_stocks(tool_input.get("timeframe", "both"))
    elif tool_name == "get_price_history":
        result = execute_get_price_history(
            tool_input["symbol"],
            tool_input.get("limit", 20)
        )
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return json.dumps(result, default=decimal_to_float)

# AI Agent
SYSTEM_PROMPT = """You are an expert stock market analyst and investment advisor 
for stockstream - a professional investment platform.

You have access to live real-time stock data through tools.
ALways call the relevant tools to get real data before answering.

Available stocks: AAPL, GOOGLE, MSFT, AMZN, TSLA

When answering:
- Always fetch real data first using tools
- Give a clear SHORT TERM view (1-7 days)
- Give a clear LONG TERM view (1-6 months)
- Explain the key technical indicators in simple terms
- Give a clear BUY/SELL/HOLD recommendation
- State the confidence level
- Keep your answer concise - 5-8 sentences maximun
- Use plain English, no jargon

ALWAYS end every response with this disclaimer on a new line:
This is technical analysis only and NOT financial advice.
Always consult a licensed financial advisor before investing.
"""

def ask_advisor(question: str) -> str:
    """
    Main function - takes a user question and returns
    AI investment adive based on real live data.
    """

    messages = [{"role": "user", "content": question}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        # Agent want to call a tool
        if response.stop_reason == "tool_use":
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({
                "role": "user",
                "content": tool_results
            })

        # AGent finished - return answer
        elif response.stop_reason == "end_turn":
            answer = ""
            for block in response.content:
                if hasattr(block, "text"):
                    answer += block.text
            return answer

        else:
            return f"Unexpected stop reason: { response.stop_reason}"

# Interactive chat

if __name__ == "__main__":
    print("=" * 60)
    print(" StockStream AI Investment Advisor")
    print(" Powered by Claude + Live Market Data")
    print(" Type 'quit' to exit")
    print("=" * 60)

    QUICK_QUESTIONS = [
        "1. Which stock should I buy right now for short term?",
        "2. Which stock is best for long term investment?",
        "3. Give me a full market overview of all 5 stocks",
        "4. Is TSLA a good buy right now?",
        "5. What is the riskiest stock right now?"
    ]

    print("\nQuick questions:")
    for q in QUICK_QUESTIONS:
        print(f"  {q}")

    while True:
        print()
        question = input("You: ").strip()

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        # Handle quick question shortcuts
        shortcuts = {
            "1": QUICK_QUESTIONS[0].split(". ", 1)[1],
            "2": QUICK_QUESTIONS[1].split(". ", 1)[1],
            "3": QUICK_QUESTIONS[2].split(". ", 1)[1],
            "4": QUICK_QUESTIONS[3].split(". ", 1)[1],
            "5": QUICK_QUESTIONS[4].split(". ", 1)[1],
        }
        if question in shortcuts:
            question = shortcuts[question]
            print(f"Asking: {question}")

        print("Advisor thinking...")
        answer = ask_advisor(question)
        print(f"\nAdvisor: {answer}")


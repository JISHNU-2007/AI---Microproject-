# agent.py
# Gemini-powered Fraud Analyst Assistant with tool/function calling.
#
# Tools:
#   get_transaction(transaction_id)       -> transaction details + prediction
#   list_risky_transactions(n, risk_level) -> top-N flagged transactions
#   get_system_stats()                    -> dashboard summary numbers
#   get_alerts()                          -> unresolved high-risk alerts
#
# Guardrails:
#   - System prompt strictly limits the agent to fraud analysis topics
#   - Uses only tool results -- never invents data
#   - Gracefully degrades if GEMINI_API_KEY is missing or API fails

import os, json
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-2.0-flash"

SYSTEM_PROMPT = (
    "You are a Fraud Analyst Assistant for SecureBank, an AI-powered fraud detection platform.\n\n"
    "Your ONLY job is to:\n"
    "1. Explain why specific transactions were flagged as fraudulent or suspicious.\n"
    "2. Answer questions about the transaction database using the provided tools.\n"
    "3. Suggest actions (Approve / Hold for Review / Block) with clear reasoning.\n"
    "4. Summarize fraud trends and risk patterns from tool data.\n\n"
    "STRICT RULES:\n"
    "- NEVER invent transaction data. Only use results returned by your tools.\n"
    "- ONLY answer questions related to fraud detection, transactions, or risk analysis.\n"
    "- If asked about anything unrelated (e.g. cooking, sports, code help), politely decline.\n"
    "- Keep responses concise, professional, and actionable. Use plain English.\n"
    "- Always cite which tool result you are using.\n"
    "- If a tool returns no data, say so clearly rather than guessing.\n"
)

TOOLS = [
    {
        "name": "get_transaction",
        "description": "Fetch full details and fraud prediction for a specific transaction ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "transaction_id": {
                    "type": "string",
                    "description": "The transaction ID (e.g. TXN-84A21)"
                }
            },
            "required": ["transaction_id"]
        }
    },
    {
        "name": "list_risky_transactions",
        "description": "List the top-N highest-risk transactions, optionally filtered by risk level.",
        "parameters": {
            "type": "object",
            "properties": {
                "n": {
                    "type": "integer",
                    "description": "Number of transactions to return (default 5)"
                },
                "risk_level": {
                    "type": "string",
                    "enum": ["High", "Review", "Low", "all"],
                    "description": "Filter by risk level. Use 'all' for no filter."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_system_stats",
        "description": "Return overall fraud detection statistics.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_alerts",
        "description": "List unresolved high-risk alerts that require human review.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max alerts to return (default 10)"}
            },
            "required": []
        }
    }
]


def _call_tool(tool_name: str, args: dict, db_session) -> str:
    import crud
    if tool_name == "get_transaction":
        txn = crud.get_transaction_by_id(db_session, args.get("transaction_id", ""))
        if not txn:
            return json.dumps({"error": f"Transaction {args.get('transaction_id')} not found."})
        return json.dumps({
            "transaction_id": txn.transaction_id,
            "channel":        txn.channel,
            "amount":         txn.amount,
            "risk_score":     txn.risk_score,
            "risk_level":     txn.risk_level,
            "decision":       txn.decision,
            "signal":         txn.signal,
            "is_fraud":       txn.is_fraud,
            "timestamp":      str(txn.timestamp),
        })

    elif tool_name == "list_risky_transactions":
        n          = args.get("n", 5)
        risk_level = args.get("risk_level", "High")
        txns = crud.get_transactions(db_session, risk_level=risk_level, limit=n)
        return json.dumps([{
            "transaction_id": t.transaction_id,
            "amount":         t.amount,
            "risk_score":     t.risk_score,
            "risk_level":     t.risk_level,
            "decision":       t.decision,
            "signal":         t.signal,
        } for t in txns])

    elif tool_name == "get_system_stats":
        stats = crud.get_stats(db_session)
        return json.dumps({k: v for k, v in stats.items() if k != "chart_data"})

    elif tool_name == "get_alerts":
        limit  = args.get("limit", 10)
        alerts = crud.get_alerts(db_session, resolved=False, limit=limit)
        return json.dumps([{
            "id":             a.id,
            "transaction_id": a.transaction_id,
            "risk_score":     a.risk_score,
            "amount":         a.amount,
            "signal":         a.signal,
        } for a in alerts])

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


def _fallback_response(message: str) -> dict:
    msg = message.lower()
    if "why" in msg or "flagged" in msg or "blocked" in msg:
        reply = (
            "I cannot connect to the AI model right now. "
            "Transactions are typically flagged due to: high velocity (many transactions in a short time), "
            "unusual amounts compared to historical averages, international location, or off-hours activity."
        )
    elif "stats" in msg or "total" in msg or "rate" in msg:
        reply = "AI model unavailable. Please check GET /api/stats for live numbers."
    elif "alert" in msg or "risky" in msg or "high risk" in msg:
        reply = "AI model unavailable. Please check GET /api/alerts for the latest high-risk transactions."
    else:
        reply = (
            "The Fraud Analyst AI is currently offline (API key may be missing). "
            "Please set GEMINI_API_KEY in backend/.env and restart the server."
        )
    return {
        "reply":             reply,
        "action_suggestion": None,
        "reasoning":         "Fallback response -- Gemini API unavailable.",
        "sources":           []
    }


def run_agent(session_id: str, user_message: str, history: list, db_session) -> dict:
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        return _fallback_response(user_message)

    try:
        import google.genai as genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)

        # Build conversation history (last 10 turns)
        contents = []
        for h in history[-10:]:
            role = "user" if h["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=h["message"])]))

        # Add current user message
        contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

        tool_declarations = [
            types.Tool(function_declarations=[
                types.FunctionDeclaration(**t) for t in TOOLS
            ])
        ]
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=tool_declarations,
            temperature=0.2,
        )

        sources_used = []
        # Agentic loop: up to 5 iterations for tool calling
        for _iteration in range(5):
            response  = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )
            candidate = response.candidates[0]
            part      = candidate.content.parts[0]

            if hasattr(part, "function_call") and part.function_call:
                fc        = part.function_call
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}
                sources_used.append(tool_name)
                tool_result = _call_tool(tool_name, tool_args, db_session)

                contents.append(types.Content(role="model", parts=[types.Part(function_call=fc)]))
                contents.append(types.Content(
                    role="tool",
                    parts=[types.Part(
                        function_response=types.FunctionResponse(
                            name=tool_name,
                            response={"result": tool_result}
                        )
                    )]
                ))
            else:
                text   = part.text if hasattr(part, "text") else str(part)
                action = None
                for kw, act in [("block", "Block"), ("approve", "Approve"),
                                 ("hold", "Hold for Review"), ("review", "Hold for Review")]:
                    if kw in text.lower():
                        action = act
                        break
                return {
                    "reply":             text,
                    "action_suggestion": action,
                    "reasoning":         None,
                    "sources":           list(dict.fromkeys(sources_used))
                }

        return {
            "reply": "I was unable to complete the analysis in the allowed steps.",
            "action_suggestion": None, "reasoning": None, "sources": sources_used
        }

    except Exception as e:
        print(f"[agent] Gemini API error: {e}")
        return _fallback_response(user_message)

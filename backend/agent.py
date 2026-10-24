# agent.py
# Groq-powered Fraud Analyst Assistant with tool/function calling.
#
# Tools:
#   get_transaction(transaction_id)        -> transaction details + prediction
#   list_risky_transactions(n, risk_level) -> top-N flagged transactions
#   get_system_stats()                     -> dashboard summary numbers
#   get_alerts()                           -> unresolved high-risk alerts
#
# Guardrails:
#   - System prompt strictly limits the agent to fraud analysis topics
#   - Uses only tool results -- never invents data
#   - Gracefully degrades if GROQ_API_KEY is missing or API fails

import os, json, re
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(ENV_PATH)
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

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
        "type": "function",
        "function": {
            "name": "get_transaction",
            "description": "Fetch full details and fraud prediction for a specific transaction ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {
                        "type": "string",
                        "description": "The transaction ID (e.g. TXN-84A21 or TXN-IC1HR)"
                    }
                },
                "required": ["transaction_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
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
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_stats",
            "description": "Return overall fraud detection statistics (total volume, alert counts, detection precision, amount saved).",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
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
    }
]


def _call_tool(tool_name: str, args: dict, db_session) -> str:
    import crud
    try:
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
                "channel":        t.channel,
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
                "channel":        a.channel,
                "signal":         a.signal,
            } for a in alerts])

        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    except Exception as e:
        return json.dumps({"error": f"Tool execution error: {str(e)}"})


def _fallback_response(message: str) -> dict:
    msg = message.lower()
    if "why" in msg or "flagged" in msg or "blocked" in msg:
        reply = (
            "Transactions are typically flagged due to: high velocity (many transactions in a short time), "
            "unusual amounts compared to historical averages, international location, or off-hours activity."
        )
    elif "stats" in msg or "total" in msg or "rate" in msg:
        reply = "Please check GET /api/stats or the Overview dashboard for live figures."
    elif "alert" in msg or "risky" in msg or "high risk" in msg:
        reply = "Please check GET /api/alerts or the Live Queue for the latest high-risk transactions."
    else:
        reply = (
            "The Fraud Analyst AI is currently offline. "
            "Please check GROQ_API_KEY in backend/.env and restart the server."
        )
    return {
        "reply":             reply,
        "action_suggestion": None,
        "reasoning":         "Fallback response -- Groq API unavailable.",
        "sources":           []
    }


def run_agent(session_id: str, user_message: str, history: list, db_session) -> dict:
    api_key = os.getenv("GROQ_API_KEY", GROQ_API_KEY)
    if not api_key or api_key == "your_groq_api_key_here":
        return _fallback_response(user_message)

    try:
        from groq import Groq

        client = Groq(api_key=api_key)

        # Build message history in OpenAI format
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        # Add recent conversation history (up to last 10 turns)
        for h in history[-10:]:
            role = "user" if h.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": h.get("message", "")})

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        sources_used = []

        # Tool execution loop (up to 5 iterations)
        for _iteration in range(5):
            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )

            choice = completion.choices[0]
            msg = choice.message

            # Check if model requested tool call(s)
            if msg.tool_calls:
                # Append assistant tool call message to history
                assistant_msg = {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        } for tc in msg.tool_calls
                    ]
                }
                messages.append(assistant_msg)

                # Execute all requested tools
                for tc in msg.tool_calls:
                    t_name = tc.function.name
                    sources_used.append(t_name)
                    try:
                        t_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except Exception:
                        t_args = {}

                    t_result = _call_tool(t_name, t_args, db_session)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": t_result,
                    })

                # Loop continues so model can use tool results to generate final response
                continue

            else:
                text = msg.content or ""
                # Strip think tags if model outputs them
                text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
                # Strip citation brackets
                text = re.sub(r"【.*?】", "", text).strip()

                # Infer action suggestion
                action = None
                text_lower = text.lower()
                for kw, act in [("block", "Block"), ("approve", "Approve"),
                                 ("hold for review", "Hold for Review"), ("hold", "Hold for Review"),
                                 ("manual review", "Hold for Review"), ("review", "Hold for Review")]:
                    if kw in text_lower:
                        action = act
                        break

                return {
                    "reply":             text,
                    "action_suggestion": action,
                    "reasoning":         None,
                    "sources":           list(dict.fromkeys(sources_used))
                }

        return {
            "reply": "I analyzed the data but could not reach a conclusion within the step limit.",
            "action_suggestion": None,
            "reasoning": None,
            "sources": list(dict.fromkeys(sources_used))
        }

    except Exception as e:
        print(f"[agent] Groq API error: {e}")
        return {
            "reply": f"⚠️ Error communicating with Groq API: {str(e)}",
            "action_suggestion": None,
            "reasoning": "Exception in agent run_agent",
            "sources": []
        }

"""
agent.py — Multi-Agent Fraud Detection Orchestrator
=====================================================
This file contains the "brain" of the system.

Instead of one big AI model doing everything, we split the work across
four specialized agents that each do one job well. This is called a
"multi-agent architecture" — a key design pattern in modern AI systems.

The four agents and what they do:
  1. RulesAgent        — runs the 4 Python fraud rules (no AI, instant)
  2. PatternAgent      — uses Claude Sonnet to find behavioral patterns
  3. RiskScorerAgent   — uses Claude Opus with deep "extended thinking"
                         to compute a 0–100 risk score
  4. CoordinatorAgent  — combines all results and writes the final answer

Why four agents instead of one?
  - Each agent has a clear, focused job → easier to understand and test
  - Agents can use different AI models (cheaper Sonnet vs powerful Opus)
  - If one agent fails, the others still run
  - The Coordinator sees all sub-results before making the final call

Self-healing:
  Every API call is wrapped in a retry loop. If the API is slow or busy,
  we wait and try again (up to 3 times). This means the system rarely
  crashes just because of a momentary network issue.
"""

import time      # for sleep() in retry logic
import json      # for converting Python dicts ↔ JSON strings
from pathlib import Path   # for finding the skills file

import anthropic   # the Anthropic Python SDK — talks to Claude

from config.settings import config                      # model names, thresholds
from observability.observability import observability   # logging and tracing
from core.governance import governance                  # compliance and audit
from core.rules import FraudDetectionRules              # the 4 Python fraud rules
from core.tools import (
    ANALYZE_TRANSACTION_TOOL,
    CHECK_CUSTOMER_HISTORY_TOOL,
    CALCULATE_FRAUD_SCORE_TOOL,
    GENERATE_FRAUD_REPORT_TOOL,
    ALL_TOOLS,
)
from core.hooks import FraudHookManager                 # pre/post middleware
from core.data import SAMPLE_TRANSACTIONS               # 22 test transactions

# ── Load the skill file as the agent's system prompt ──────────────
# The skill file (fraud_detection.md) tells each Claude agent what it is,
# what rules to follow, and how to format its response.
# This is called a "skill" — a reusable prompt template for the agent.
_SKILL_PATH = Path(__file__).parent / "skills" / "fraud_detection.md"
_SKILL_TEXT = _SKILL_PATH.read_text(encoding="utf-8") if _SKILL_PATH.exists() else ""


class FraudDetectionOrchestrator:
    """
    The main class that coordinates all four agents.

    Usage (from app.py):
        orchestrator = FraudDetectionOrchestrator()
        result = orchestrator.analyze(transaction, all_transactions)
        print(result["risk_level"])   # "Safe", "Suspicious", or "High Risk"
    """

    def __init__(self):
        # Create the Anthropic client — this is our connection to Claude
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        # The Python rule engine (no AI needed for this one)
        self.rules  = FraudDetectionRules()
        # The hooks middleware (validates inputs, logs decisions)
        self.hooks  = FraudHookManager()

    # ──────────────────────────────────────────────────────────────
    # MAIN METHOD: analyze()
    # This is the entry point. Call this method with one transaction
    # and get back a full fraud analysis result.
    # ──────────────────────────────────────────────────────────────

    def analyze(self, raw_txn: dict, all_transactions: list | None = None) -> dict:
        """
        Run the full 4-agent fraud detection pipeline on one transaction.

        What happens step by step:
          1. pre_process hook: validate the transaction, assign a unique tracking ID
          2. RulesAgent: check all 4 Python fraud rules (instant, no API call)
          3. PatternAgent: ask Claude Sonnet about behavioral patterns
          4. RiskScorerAgent: ask Claude Opus (with deep thinking) for a risk score
          5. CoordinatorAgent: synthesize everything into a final decision
          6. post_process hook: write to audit log, check compliance

        Parameters:
            raw_txn          (dict): one transaction from data.py
            all_transactions (list): all transactions (needed for rapid succession check)

        Returns:
            A dict with: risk_level, fraud_reasons, risk_score, explanation,
                         agent_trace, and correlation_id
        """
        if all_transactions is None:
            all_transactions = SAMPLE_TRANSACTIONS

        # ── Step 1: Pre-process hook ───────────────────────────────
        # This validates the transaction and adds a unique "correlation_id"
        # (a UUID like "550e8400-e29b-41d4-a716-446655440000") so we can
        # trace this transaction through all 4 agent calls in the logs.
        try:
            txn = self.hooks.pre_process(raw_txn)
        except ValueError as e:
            # Validation failed (e.g. missing fields) — return a safe error result
            return self.hooks.on_error(e, {"transaction_id": raw_txn.get("transaction_id", "?")})

        cid   = txn["correlation_id"]   # the unique tracking ID for this request
        trace = []   # records which agents ran, shown in the dashboard

        try:
            # ── Step 2: Rules Agent (no LLM — pure Python) ────────
            # Fast and deterministic. Always runs first because it's free
            # and tells the AI agents what the Python rules found.
            t0 = time.time()
            rules_result = self._run_rules_agent(txn, all_transactions)
            # Record how long this agent took (for the observability dashboard)
            observability.trace(
                cid, "RulesAgent",
                {"txn_id": txn["transaction_id"]},
                {"risk_level": rules_result["risk_level"]},
                (time.time() - t0) * 1000   # convert seconds to milliseconds
            )
            trace.append({"agent": "RulesAgent", "result": rules_result["risk_level"]})

            # ── Step 3: Pattern Agent (Claude Sonnet) ─────────────
            # Sends the transaction + rules result to Claude Sonnet and asks:
            # "Does this transaction fit any known fraud behavior pattern?"
            # We use the cheaper Sonnet model here to keep costs down.
            t0 = time.time()
            pattern_result = self._run_pattern_agent(txn, rules_result)
            observability.trace(
                cid, "PatternAgent",
                {"txn_id": txn["transaction_id"]},
                {"analysis": pattern_result.get("analysis", "")[:100]},
                (time.time() - t0) * 1000
            )
            trace.append({
                "agent": "PatternAgent",
                "analysis_snippet": pattern_result.get("analysis", "")[:80]
            })

            # ── Step 4: Risk Scorer Agent (Claude Opus + Extended Thinking) ──
            # This is the most powerful agent. It uses "extended thinking" which
            # means Claude reasons step-by-step (like writing scratch work) before
            # answering. This produces a more accurate risk score.
            # We give it 5,000 "thinking tokens" to reason with.
            t0 = time.time()
            risk_result = self._run_risk_scorer_agent(txn, rules_result, pattern_result)
            observability.trace(
                cid, "RiskScorerAgent",
                {"txn_id": txn["transaction_id"]},
                {"risk_score": risk_result.get("risk_score")},
                (time.time() - t0) * 1000
            )
            trace.append({
                "agent": "RiskScorerAgent",
                "risk_score": risk_result.get("risk_score")
            })

            # ── Step 5: Coordinator Agent (Claude Opus) ───────────
            # The coordinator reads all three sub-agent results and
            # writes the final decision + customer-facing explanation.
            t0 = time.time()
            final = self._run_coordinator_agent(
                txn, rules_result, pattern_result, risk_result
            )
            observability.trace(
                cid, "CoordinatorAgent",
                {"txn_id": txn["transaction_id"]},
                {"final_decision": final.get("risk_level")},
                (time.time() - t0) * 1000
            )
            trace.append({
                "agent": "CoordinatorAgent",
                "final_decision": final.get("risk_level")
            })

        except Exception as e:
            # If ANYTHING goes wrong, return a safe "Suspicious" result instead of crashing.
            # A human analyst will review it. This is our self-healing behavior.
            return self.hooks.on_error(e, {
                "correlation_id": cid,
                "transaction_id": txn.get("transaction_id", "?"),
            })

        # Attach the agent trace so the dashboard can show which agents ran
        final["agent_trace"]   = trace
        # Store original transaction for fairness check in post_process
        final["_original_txn"] = raw_txn

        # ── Step 6: Post-process hook ──────────────────────────────
        # Writes to the audit log, checks compliance, flags unfair decisions
        return self.hooks.post_process(final, cid)

    # ──────────────────────────────────────────────────────────────
    # BATCH METHOD: analyze_all()
    # Runs analyze() on every transaction in the list.
    # Called by the "Run Fraud Analysis" button in app.py.
    # ──────────────────────────────────────────────────────────────

    def analyze_all(self, transactions: list | None = None) -> list[dict]:
        """
        Analyze every transaction in a list.
        Returns a list of results, one per transaction.
        """
        txns    = transactions or SAMPLE_TRANSACTIONS
        results = []
        for txn in txns:
            result = self.analyze(txn, all_transactions=txns)
            results.append(result)
        return results

    # ──────────────────────────────────────────────────────────────
    # SUB-AGENT 1: Rules Agent (pure Python, no API call)
    # ──────────────────────────────────────────────────────────────

    def _run_rules_agent(self, txn: dict, all_transactions: list) -> dict:
        """
        Run all four fraud rules using plain Python.
        No Claude API call — this is instant and free.
        The result tells the AI agents what the rules found,
        so they don't have to re-check the same conditions.
        """
        # delegates to FraudDetectionRules.evaluate() in rules.py
        return self.rules.evaluate(txn, all_transactions)

    # ──────────────────────────────────────────────────────────────
    # SUB-AGENT 2: Pattern Agent (Claude Sonnet)
    # ──────────────────────────────────────────────────────────────

    def _run_pattern_agent(self, txn: dict, rules_result: dict) -> dict:
        """
        Ask Claude Sonnet to analyze the behavioral context of this transaction.

        Questions it answers:
        - Is this transaction unusual for this customer's history?
        - Does it match a known fraud pattern (e.g. card-not-present fraud)?
        - Are there any soft signals the rule engine might have missed?

        We use claude-sonnet-4-6 (not Opus) here because:
        - Pattern analysis is less complex than deep risk scoring
        - Sonnet is faster and cheaper
        - We save the expensive Opus model for the Risk Scorer
        """
        # The system prompt = skill instructions + pattern specialist role
        system = (
            _SKILL_TEXT + "\n\n"
            "You are the Pattern Detection specialist in a multi-agent fraud system. "
            "Analyze this transaction's behavioral context: is it unusual for the customer? "
            "What fraud pattern does it match? Keep your analysis under 3 sentences."
        )

        # Build the user message with all transaction details
        user_msg = (
            f"Transaction: {txn['transaction_id']}\n"
            f"Customer: {txn['customer_id']}\n"
            f"Amount: ₹{float(txn['amount']):,.0f}\n"
            f"Location: {txn['location']}\n"
            f"Type: {txn['transaction_type']}\n"
            f"Time: {txn['time']}\n\n"
            f"Rules Engine Result: {rules_result['risk_level']}\n"
            f"Triggered rules: {', '.join(rules_result['fraud_reasons']) or 'None'}\n\n"
            "Briefly describe the behavioral pattern and any additional concerns."
        )

        def _call():
            """The actual API call — wrapped in a function so _retry() can call it again."""
            return self.client.messages.create(
                model=config.FALLBACK_MODEL,   # claude-sonnet-4-6 — cheaper, still good
                max_tokens=512,                # short response is fine for pattern analysis
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )

        # _retry() will try up to 3 times if the API call fails
        response = self._retry(_call)

        # Extract the text from Claude's response
        analysis = ""
        for block in response.content:
            if hasattr(block, "type") and block.type == "text":
                analysis = block.text
                break

        return {"analysis": analysis}

    # ──────────────────────────────────────────────────────────────
    # SUB-AGENT 3: Risk Scorer Agent (Claude Opus + Extended Thinking)
    # ──────────────────────────────────────────────────────────────

    def _run_risk_scorer_agent(
        self, txn: dict, rules_result: dict, pattern_result: dict
    ) -> dict:
        """
        Use Claude Opus with extended thinking to compute a 0–100 risk score.

        What is "extended thinking"?
          Normally Claude reads your prompt and immediately writes an answer.
          With extended thinking enabled, Claude first writes down its reasoning
          (like scratch work on paper) before writing the final answer.
          This produces better results for complex decisions.

        Why a 0–100 score?
          A score is easier to explain to humans than just Safe/Suspicious/High Risk.
          The dashboard shows it as a speedometer gauge.

        This agent uses a TOOL CALL to return the score in a structured format.
        A "tool call" is when Claude says "I want to call this function with these inputs"
        instead of just writing free text. We then run the function ourselves and
        send the result back to Claude so it can continue.
        """
        system = (
            _SKILL_TEXT + "\n\n"
            "You are the Risk Scoring specialist. "
            "Use extended thinking to reason deeply about the overall fraud risk. "
            "Then call the calculate_fraud_score tool with your evaluation. "
            "Set each flag to True if that fraud condition applies."
        )
        user_msg = (
            f"Transaction: {txn['transaction_id']}, "
            f"₹{float(txn['amount']):,.0f}, "
            f"{txn['location']}, {txn['transaction_type']}\n"
            f"Rules Engine result: {rules_result['risk_level']}\n"
            f"Pattern analysis: {pattern_result.get('analysis', 'N/A')}\n\n"
            "Reason through the fraud risk carefully, then call calculate_fraud_score."
        )

        def _call():
            return self.client.messages.create(
                model=config.PRIMARY_MODEL,    # claude-opus-4-8 — most capable
                max_tokens=config.MAX_TOKENS,
                thinking={
                    "type": "enabled",
                    "budget_tokens": config.THINKING_BUDGET,  # 5000 tokens for reasoning
                },
                system=system,
                messages=[{"role": "user", "content": user_msg}],
                tools=[CALCULATE_FRAUD_SCORE_TOOL],   # Claude can call this tool
            )

        response = self._retry(_call)
        # Handle the tool-use response loop (see _extract_risk_score below)
        return self._extract_risk_score(response, rules_result, txn)

    def _extract_risk_score(self, response, rules_result: dict, txn: dict) -> dict:
        """
        Handle the tool-use conversation loop with the Risk Scorer.

        When Claude wants to call a tool, the API returns stop_reason="tool_use".
        We then:
          1. Read the tool name and inputs Claude provided
          2. Run the actual calculation ourselves (Python function)
          3. Send the result back to Claude
          4. Claude then continues and gives its final answer

        This back-and-forth can happen multiple times until Claude is done.
        """
        risk_score = rules_result.get("risk_score", 0.0)  # default from rules engine
        thinking   = ""                      # will store Claude's reasoning text
        messages   = [{"role": "user", "content": "Score the fraud risk"}]
        current    = response

        # Keep looping while Claude still wants to call tools
        while current.stop_reason == "tool_use":
            tool_results = []

            for block in current.content:
                if block.type == "thinking":
                    # Claude wrote its reasoning — save it for display
                    thinking = block.thinking

                elif block.type == "tool_use" and block.name == "calculate_fraud_score":
                    # Claude wants to call calculate_fraud_score with these inputs
                    inp = block.input

                    # We compute the risk score ourselves using Python
                    risk_score = _compute_risk_score(
                        inp.get("high_amount_triggered", False),
                        inp.get("unusual_location_triggered", False),
                        inp.get("rapid_succession_triggered", False),
                        inp.get("international_triggered", False),
                        float(inp.get("amount", txn.get("amount", 0))),
                    )

                    # Format the result as a "tool_result" message to send back
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,   # must match the tool_use block's id
                        "content":     json.dumps({"risk_score": risk_score}),
                    })

            if not tool_results:
                break   # Claude didn't call any tools → we're done

            # Add Claude's message + our tool results to the conversation history
            messages.append({"role": "assistant", "content": current.content})
            messages.append({"role": "user",      "content": tool_results})

            # Continue the conversation — Claude will now read the tool result
            current = self._retry(lambda: self.client.messages.create(
                model=config.PRIMARY_MODEL,
                max_tokens=config.MAX_TOKENS,
                system="You are a risk scoring specialist.",
                messages=messages,
                tools=[CALCULATE_FRAUD_SCORE_TOOL],
            ))

        # Grab any thinking block from the final response
        for block in current.content:
            if hasattr(block, "type") and block.type == "thinking":
                thinking = block.thinking

        return {
            "risk_score":      risk_score,
            "thinking_summary": thinking[:400] if thinking else "",  # first 400 chars
        }

    # ──────────────────────────────────────────────────────────────
    # SUB-AGENT 4: Coordinator Agent (Claude Opus)
    # ──────────────────────────────────────────────────────────────

    def _run_coordinator_agent(
        self,
        txn: dict,
        rules_result: dict,
        pattern_result: dict,
        risk_result: dict,
    ) -> dict:
        """
        Synthesize results from all three specialist agents into a final decision.

        The Coordinator sees:
          - What the Rules Agent found (Python rule results)
          - What the Pattern Agent found (behavioral analysis)
          - What the Risk Scorer found (0–100 score)

        It then calls the generate_fraud_report tool to write a structured report.
        The report includes:
          - Final risk classification (Safe / Suspicious / High Risk)
          - Customer-facing explanation in plain English
          - Recommended action (none / alert_customer / block_transaction)
        """
        system = (
            _SKILL_TEXT + "\n\n"
            "You are the Coordinator Agent. You have received reports from three specialist agents. "
            "Synthesize their findings and call generate_fraud_report "
            "to produce the final fraud classification and a clear explanation."
        )

        # Pull out key values from previous agents
        risk_level    = rules_result.get("risk_level", "Suspicious")
        fraud_reasons = rules_result.get("fraud_reasons", [])
        risk_score    = risk_result.get("risk_score", 0.0)
        recommended   = _recommend_action(risk_level, risk_score)

        # Tell the Coordinator everything the other agents found
        user_msg = (
            f"Transaction: {txn['transaction_id']}\n"
            f"Customer: {txn['customer_id']}\n"
            f"Amount: ₹{float(txn['amount']):,.0f}, Location: {txn['location']}\n"
            f"Type: {txn['transaction_type']}, Time: {txn['time']}\n\n"
            f"--- Rules Agent Result ---\n"
            f"Risk Level: {risk_level}\n"
            f"Fraud Reasons: {', '.join(fraud_reasons) or 'No flags triggered'}\n\n"
            f"--- Pattern Detector Result ---\n"
            f"{pattern_result.get('analysis', 'N/A')[:200]}\n\n"
            f"--- Risk Scorer Result ---\n"
            f"Risk Score: {risk_score}/100\n"
            f"Suggested Action: {recommended}\n\n"
            "Now call generate_fraud_report with the final classification."
        )

        messages = [{"role": "user", "content": user_msg}]

        def _call():
            return self.client.messages.create(
                model=config.PRIMARY_MODEL,
                max_tokens=config.MAX_TOKENS,
                system=system,
                messages=messages,
                tools=[GENERATE_FRAUD_REPORT_TOOL],
            )

        response    = self._retry(_call)
        explanation = ""

        # Tool-use loop: Claude will call generate_fraud_report
        while response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use" and block.name == "generate_fraud_report":
                    inp = block.input
                    # Build the human-readable explanation from the tool input
                    explanation = _build_explanation(inp)
                    # Coordinator can override the risk level if it disagrees with rules
                    risk_level = inp.get("risk_level", risk_level)
                    risk_score = inp.get("risk_score", risk_score)
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     json.dumps({"report": explanation}),
                    })

            if not tool_results:
                break   # no tool call → Claude gave a plain text response

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user",      "content": tool_results})

            response = self._retry(lambda: self.client.messages.create(
                model=config.PRIMARY_MODEL,
                max_tokens=config.MAX_TOKENS,
                system=system,
                messages=messages,
                tools=[GENERATE_FRAUD_REPORT_TOOL],
            ))

        # Fallback: if Claude gave plain text instead of a tool call, use that
        if not explanation:
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    explanation = block.text
                    break
            # If still empty, build a basic explanation from the rule results
            if not explanation:
                explanation = _auto_explanation(txn, risk_level, fraud_reasons, risk_score)

        return {
            "transaction_id":    txn["transaction_id"],
            "risk_level":        risk_level,       # "Safe", "Suspicious", or "High Risk"
            "fraud_reasons":     fraud_reasons,    # list of triggered rule messages
            "risk_score":        risk_score,       # 0–100
            "explanation":       explanation,      # human-readable explanation for dashboard
            "recommended_action": recommended,     # what the bank should do
            "confidence":        _confidence(risk_level, risk_score),
            "pattern_analysis":  pattern_result.get("analysis", ""),
        }

    # ──────────────────────────────────────────────────────────────
    # SELF-HEALING: Retry with exponential backoff
    # If an API call fails, we wait and try again automatically.
    # This handles temporary issues like network timeouts or API rate limits.
    # ──────────────────────────────────────────────────────────────

    def _retry(self, fn, max_retries: int = config.MAX_RETRIES):
        """
        Call a function. If it fails, wait and try again up to max_retries times.

        Exponential backoff means we wait longer between each retry:
          Attempt 1 fails → wait 1 second
          Attempt 2 fails → wait 2 seconds
          Attempt 3 fails → wait 4 seconds
          Still failing   → raise the error so on_error() can handle it

        This is called "exponential backoff" — a standard technique to avoid
        hammering an API that's already struggling.

        Parameters:
            fn (callable): the function to call (usually a lambda that calls the API)
            max_retries: how many times to try before giving up
        """
        last_err = None
        for attempt in range(max_retries):
            try:
                return fn()   # Try to call the function
            except anthropic.RateLimitError as e:
                # API is too busy — wait and retry
                wait = config.RETRY_BASE_DELAY * (2 ** attempt)  # 1s, 2s, 4s
                time.sleep(wait)
                last_err = e
            except anthropic.APIError as e:
                if attempt == max_retries - 1:
                    last_err = e
                    break   # out of retries
                time.sleep(config.RETRY_BASE_DELAY * (2 ** attempt))
                last_err = e

        # All retries failed — raise so the caller's except block handles it
        raise RuntimeError(f"API call failed after {max_retries} retries: {last_err}")


# ──────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS (used by the agents above)
# ──────────────────────────────────────────────────────────────────

def _compute_risk_score(
    high_amount: bool,
    unusual_loc: bool,
    rapid: bool,
    intl: bool,
    amount: float,
) -> float:
    """
    Calculate a numeric fraud risk score from 0 (safe) to 100 (very risky).
    Called when the Risk Scorer agent's tool call comes back.

    Each fraud condition adds a certain number of points:
      High amount    → up to 50 points (35 base + up to 15 for very large amounts)
      Unusual location → 30 points (strong signal — known fraud area)
      Rapid succession → 25 points (velocity fraud pattern)
      International   → 15 points (weakest signal — might just be travelling)

    The total is capped at 100 so the gauge never overflows.
    """
    score = 0.0

    if high_amount:
        # Add up to 15 bonus points for very large amounts (scales with size)
        score += 35 + min(15, (amount - config.HIGH_AMOUNT_THRESHOLD) / 10000)

    if unusual_loc:
        score += 30.0

    if rapid:
        score += 25.0

    if intl:
        score += 15.0

    # Never go above 100
    return round(min(100.0, score), 1)


def _recommend_action(risk_level: str, risk_score: float) -> str:
    """
    Map a risk level and score to what the bank should do.

    High Risk or score ≥ 70  → block the transaction immediately
    Suspicious or score ≥ 40 → send the customer a fraud alert
    Safe                     → do nothing (normal transaction)
    """
    if risk_level == "High Risk" or risk_score >= 70:
        return "block_transaction"    # stop the money from moving
    elif risk_level == "Suspicious" or risk_score >= 40:
        return "alert_customer"       # text/email the customer
    else:
        return "none"                 # transaction looks fine


def _confidence(risk_level: str, risk_score: float) -> float:
    """
    Estimate how confident the system is in its decision (0.0 to 1.0).
    This is a simple heuristic — a real system would use calibration data.
    """
    if risk_level == "Safe":
        # Lower score = safer = more confident
        return round(1.0 - risk_score / 200, 2)
    elif risk_level == "High Risk":
        # Higher score = riskier = more confident it's fraud
        return round(0.5 + risk_score / 200, 2)
    return 0.70   # Suspicious: moderately confident


def _build_explanation(inp: dict) -> str:
    """
    Build a human-readable fraud report from the generate_fraud_report tool inputs.
    This is what gets shown in the dashboard's "AI Explanation" section.

    Parameters:
        inp (dict): the inputs Claude provided to generate_fraud_report
    """
    txn_id   = inp.get("transaction_id", "?")
    risk     = inp.get("risk_level", "Suspicious")
    reasons  = inp.get("fraud_reasons", [])
    score    = inp.get("risk_score", 0)
    action   = inp.get("recommended_action", "monitor")
    amount   = inp.get("amount", 0)
    location = inp.get("location", "?")

    # Pick an icon based on risk level
    icon = {"Safe": "✅", "Suspicious": "⚠️", "High Risk": "🚨"}.get(risk, "⚠️")

    lines = [
        f"**Transaction {txn_id} — {icon} {risk.upper()}**",
        "",
        f"Amount: ₹{float(amount):,.0f} | Location: {location}",
        "",
    ]

    if reasons:
        lines.append("**Fraud Indicators Detected:**")
        for r in reasons:
            lines.append(f"  • {r}")     # bullet point for each fraud reason
    else:
        lines.append("**No fraud indicators detected.** Transaction passed all checks.")

    lines += [
        "",
        f"**Risk Score:** {score}/100",
        f"**Recommended Action:** {action.replace('_', ' ').title()}",
    ]

    return "\n".join(lines)


def _auto_explanation(txn: dict, risk_level: str, reasons: list, score: float) -> str:
    """
    Basic fallback explanation when Claude doesn't call the generate_fraud_report tool.
    Builds a plain text summary directly from the rule results.
    """
    icon  = {"Safe": "✅", "Suspicious": "⚠️", "High Risk": "🚨"}.get(risk_level, "⚠️")
    parts = [f"**{txn['transaction_id']} — {icon} {risk_level}**", ""]

    if reasons:
        parts.append("Fraud reasons:")
        for r in reasons:
            parts.append(f"  • {r}")
    else:
        parts.append("No fraud indicators found. Transaction is safe.")

    parts.append(f"\nRisk Score: {score}/100")
    return "\n".join(parts)

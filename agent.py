from dotenv import load_dotenv
import logging
import asyncio
import os
import re
from typing import List, Dict

from livekit import agents
from livekit.agents import (
    AgentSession,
    Agent,
    RoomInputOptions,
    ChatContext,
    RunContext,
    function_tool,
)
from livekit.plugins import noise_cancellation
from livekit.plugins import google

from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import get_weather, search_web, send_email, get_local_time
from mem0 import AsyncMemoryClient

load_dotenv()
logging.basicConfig(level=logging.INFO)

USER_ID = os.getenv("USER_ID", "Bruce Wayne").strip()

# -------------------------
# Memory tuning knobs
# -------------------------
# How many memories to return per recall tool call
MEMORY_RECALL_LIMIT = int(os.getenv("MEMORY_RECALL_LIMIT", "50"))

# How many memories to preload at the start of each session (recent context)
RECENT_MEMORY_LIMIT = int(os.getenv("RECENT_MEMORY_LIMIT", "60"))

# How many "SESSION SUMMARY" memories to preload (high-signal history)
SESSION_SUMMARY_LIMIT = int(os.getenv("SESSION_SUMMARY_LIMIT", "10"))


# -------------------------
# Noise filtering helpers
# -------------------------
def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _is_noise(text: str, role: str) -> bool:
    t = _normalize_text(text).lower()
    if not t:
        return True

    # very short -> noise
    if len(t) < 12:
        return True

    # common greeting/small-talk/bye patterns (user + assistant)
    small_talk_patterns = [
        r"\bhi\b", r"\bhello\b", r"\bhey\b",
        r"how are you", r"how you doing", r"what's up", r"wassup",
        r"good morning", r"good afternoon", r"good evening", r"good night",
        r"\bbye\b", r"bye bye", r"see you", r"take care", r"goodbye",
        r"thank you", r"thanks", r"thx", r"ok\b", r"okay\b", r"alright\b",
        r"nice", r"cool", r"great", r"perfect", r"fine",
    ]
    for pat in small_talk_patterns:
        if re.search(pat, t):
            # if it's basically just small talk, treat as noise
            if len(t) < 60:
                return True

    # assistant acknowledgements are noise
    if role == "assistant":
        if t.startswith(("sure", "okay", "alright", "done", "got it", "of course", "will do", "check", "noted")):
            return True

    return False

def _looks_like_tool_dump(text: str) -> bool:
    """
    Drop giant blocks that are tool output noise (web search dumps, long lists, etc.)
    Tune these patterns if needed.
    """
    t = text.lower()
    if "relevant memories:" in t:
        return True
    if len(text) > 1500:
        return True
    return False


def _make_session_summary(filtered_msgs: List[Dict[str, str]]) -> str:
    """
    Compact recap to keep long-term memory useful and scalable.
    Heuristic summary: last ~8 user messages + last ~4 assistant messages (trimmed).
    """
    user_lines = [m["content"] for m in filtered_msgs if m["role"] == "user"]
    asst_lines = [m["content"] for m in filtered_msgs if m["role"] == "assistant"]

    last_user = user_lines[-8:]
    last_asst = asst_lines[-4:]

    if not last_user and not last_asst:
        return ""

    # Keep it compact
    parts = []
    if last_user:
        parts.append("User: " + " | ".join(_normalize_text(x) for x in last_user))
    if last_asst:
        parts.append("Assistant: " + " | ".join(_normalize_text(x) for x in last_asst))

    summary = "SESSION SUMMARY: " + " || ".join(parts)
    return summary[:900]  # hard cap to avoid bloating memory

def _fingerprint(text: str) -> str:
    # Normalize hard for dedupe
    t = _normalize_text(text).lower()
    # remove trailing punctuation noise
    t = re.sub(r"[^\w\s]+$", "", t)
    return t


async def _load_recent_memory_fingerprints(mem_client, user_id: str, limit: int = 250) -> set[str]:
    """
    Pull a bunch of recent memories and create a fingerprint set so we don't re-store the same content.
    """
    fp: set[str] = set()
    try:
        resp = await mem_client.search(
            query="recent conversation important facts preferences ongoing tasks decisions",
            filters={"user_id": user_id},
            limit=limit,
        )
        results = resp.get("results", []) or []
        for r in results:
            m = (r.get("memory") or "").strip()
            if m:
                fp.add(_fingerprint(m))
    except Exception as e:
        logging.error(f"❌ Failed to load recent memory fingerprints: {e}")
    return fp


async def _get_latest_session_summary(mem_client, user_id: str) -> str:
    """
    Fetch the latest SESSION SUMMARY (if any) to avoid storing the same summary repeatedly.
    """
    try:
        resp = await mem_client.search(
            query="SESSION SUMMARY:",
            filters={"user_id": user_id},
            limit=1,
        )
        results = resp.get("results", []) or []
        if results:
            return (results[0].get("memory") or "").strip()
    except Exception as e:
        logging.error(f"❌ Failed to fetch latest session summary: {e}")
    return ""

async def entrypoint(ctx: agents.JobContext):
    mem_client = AsyncMemoryClient()

    # -------------------------
    # MEMORY RECALL TOOL (LIVE)
    # -------------------------
    @function_tool()
    async def recall_memory(context: RunContext, query: str) -> str:  # type: ignore
        """
        Search mem0 for user-specific facts. Use for personal questions like name, favorites, preferences, etc.
        """
        try:
            resp = await mem_client.search(
                query=query,
                filters={"user_id": USER_ID},
                limit=MEMORY_RECALL_LIMIT,
            )
            results = resp.get("results", []) or []
            facts = [r.get("memory", "").strip() for r in results if r.get("memory")]
            if not facts:
                return "No relevant memory found."
            return "Relevant memories:\n" + "\n".join(f"- {f}" for f in facts)
        except Exception as e:
            logging.error(f"❌ recall_memory failed: {e}")
            return "Memory lookup failed."

    # -------------------------
    # STARTUP: PRELOAD HIGH-SIGNAL MEMORY
    # -------------------------
    known_facts_lines: list[str] = []

    # (A) Load recent "SESSION SUMMARY" memories (cleanest signal)
    try:
        resp_sum = await mem_client.search(
            query="SESSION SUMMARY:",
            filters={"user_id": USER_ID},
            limit=SESSION_SUMMARY_LIMIT,
        )
        sum_results = resp_sum.get("results", []) or []
        for r in sum_results:
            m = (r.get("memory") or "").strip()
            if m:
                known_facts_lines.append(f"- {m}")
        logging.info(f"✅ Loaded {len(sum_results)} session summaries for startup context")
    except Exception as e:
        logging.error(f"❌ Session summary preload failed: {e}")

    # (B) Load recent general memories (still useful, but can be noisy)
    try:
        resp_recent = await mem_client.search(
            query="recent conversation important facts preferences ongoing tasks decisions",
            filters={"user_id": USER_ID},
            limit=RECENT_MEMORY_LIMIT,
        )
        recent_results = resp_recent.get("results", []) or []
        for r in recent_results:
            m = (r.get("memory") or "").strip()
            if m:
                known_facts_lines.append(f"- {m}")
        logging.info(f"✅ Loaded {len(recent_results)} recent memories for startup context")
    except Exception as e:
        logging.error(f"❌ Recent memory preload failed: {e}")

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for line in known_facts_lines:
        if line not in seen:
            seen.add(line)
            deduped.append(line)
    known_facts_lines = deduped

    # IMPORTANT: Match your prompts.py expectation exactly:
    # "KNOWN FACTS ABOUT MR. WAYNE"
    memory_block = ""
    if known_facts_lines:
        memory_block = "\n\n# KNOWN FACTS ABOUT MR. WAYNE\n" + "\n".join(known_facts_lines) + "\n"

    # -------------------------
    # STRICT RULES
    # -------------------------
    strict_rules = f"""
# ABSOLUTE RULES (CRITICAL)
- Always include "Mr. Wayne" in every response (at least once).
- If asked date/time: ALWAYS call get_local_time. Never guess.
- If asked weather: ALWAYS call get_weather (ask city if missing).
- If asked to send email: ALWAYS call send_email. Never fake it.

# MEMORY USAGE (CRITICAL)
- You have a tool called recall_memory(query).
- For ANY personal question (name/full name, favorites, preferences, likes/dislikes, email):
  1) FIRST call recall_memory with the relevant query.
  2) Answer ONLY using the returned memories.
  3) If recall_memory returns "No relevant memory found.", ask ONE short follow-up question.
"""

    combined_instructions = AGENT_INSTRUCTION + memory_block + "\n" + strict_rules

    # -------------------------
    # CREATE SESSION + AGENT
    # -------------------------
    session = AgentSession()
    agent = Agent(
        instructions=combined_instructions,
        llm=google.beta.realtime.RealtimeModel(
            voice="aoede",
            temperature=1.2,
        ),
        tools=[
            get_weather,
            search_web,
            send_email,
            get_local_time,
            recall_memory,
        ],
        chat_ctx=ChatContext(),
    )

    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(
            video_enabled=True,
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()
    await session.generate_reply(instructions=SESSION_INSTRUCTION)

    # -------------------------
    # SAVE CHAT ON EXIT (SMART + LOW NOISE)
    # -------------------------
    async def save_full_chat():
        logging.info("💾 Saving high-signal memory only")

        raw_messages = []

        for item in agent.chat_ctx.items:
            role = getattr(item, "role", None)
            content = getattr(item, "content", None)

            if role not in ["user", "assistant", "model"]:
                continue

            normalized_role = "assistant" if role == "model" else role
            text = "".join(content) if isinstance(content, list) else str(content)
            text = _normalize_text(text)

            if not text:
                continue

            raw_messages.append({"role": normalized_role, "content": text})

        if not raw_messages:
            return

        # Create compact session summary
        summary = _make_session_summary(raw_messages)

        if not summary:
            return

        # Check if this summary already exists
        latest_summary = await _get_latest_session_summary(mem_client, USER_ID)

        if _fingerprint(summary) == _fingerprint(latest_summary):
            logging.info("ℹ️ Session summary unchanged. Skipping save.")
            return

        try:
            await mem_client.add(
                [{"role": "user", "content": summary}],
                user_id=USER_ID,
                infer=True,   # Only infer from summary
            )
            logging.info("✅ Saved SESSION SUMMARY only")
        except Exception as e:
            logging.error(f"❌ Failed saving summary: {e}")

    ctx.add_shutdown_callback(lambda: asyncio.create_task(save_full_chat()))


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
from dotenv import load_dotenv
import logging
import asyncio
import os

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, ChatContext, RunContext, function_tool
from livekit.plugins import noise_cancellation
from livekit.plugins import google

from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import get_weather, search_web, send_email, get_local_time
from mem0 import AsyncMemoryClient

load_dotenv()
logging.basicConfig(level=logging.INFO)

USER_ID = os.getenv("USER_ID", "Bruce Wayne").strip()


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
                limit=10,
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
    # LOAD SOME MEMORY (FOR STARTUP PERSONALITY)
    # -------------------------
    known_facts_lines: list[str] = []
    try:
        resp = await mem_client.search(
            query="user preferences personal facts favorites name full name email",
            filters={"user_id": USER_ID},
            limit=30,
        )
        results = resp.get("results", []) or []
        for r in results:
            m = (r.get("memory") or "").strip()
            if m:
                known_facts_lines.append(f"- {m}")
        logging.info(f"✅ Loaded {len(known_facts_lines)} memories for startup context")
    except Exception as e:
        logging.error(f"❌ Memory preload failed: {e}")

    memory_block = ""
    if known_facts_lines:
        memory_block = "\n\n# Known user facts (from mem0)\n" + "\n".join(known_facts_lines) + "\n"

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
  3) If recall_memory returns "No relevant memory found.", ask ONE short follow-up question and store it later via normal chat saving.

Examples:
- User: "What is my full name?"
  -> call recall_memory("full name name")
  -> answer using returned line
"""

    # Build final instructions for the agent
    combined_instructions = AGENT_INSTRUCTION + memory_block + "\n" + strict_rules

    # -------------------------
    # CREATE SESSION + AGENT
    # -------------------------
    session = AgentSession()
    agent = Agent(
        instructions=combined_instructions,
        llm=google.beta.realtime.RealtimeModel(
            voice="aoede",
            temperature=1.0,
        ),
        tools=[
            get_weather,
            search_web,
            send_email,
            get_local_time,
            recall_memory,   # ✅ NEW
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
    # SAVE CHAT ON EXIT (SAFE)
    # -------------------------
    async def save_full_chat():
        logging.info("💾 Saving chat transcript to mem0")

        messages = []
        for item in agent.chat_ctx.items:
            role = getattr(item, "role", None)
            content = getattr(item, "content", None)
            if role is None or content is None:
                continue
            if role not in ["user", "assistant", "model"]:
                continue

            normalized_role = "assistant" if role == "model" else role
            text = "".join(content) if isinstance(content, list) else str(content)
            text = text.strip()
            if not text:
                continue

            messages.append({"role": normalized_role, "content": text})

        if not messages:
            return

        try:
            await mem_client.add(messages, user_id=USER_ID, infer=True)
            logging.info(f"✅ Saved {len(messages)} messages to mem0")
        except Exception as e:
            logging.error(f"❌ Failed saving to mem0: {e}")

    ctx.add_shutdown_callback(lambda: asyncio.create_task(save_full_chat()))


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))

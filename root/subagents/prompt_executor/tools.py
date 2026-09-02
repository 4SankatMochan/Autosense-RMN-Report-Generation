from root.subagents.data_science.agent import root_agent
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
import asyncio
import logging
import random
import time

from .subagents.Campaign_analysis.tools import campaign_analysis_agent
from .subagents.Campaign_comparison.tools import campaign_comparison_agent
from .subagents.Recommendation.tools import recommendation_agent
from .subagents.Executive_summary.tools import executive_summary_agent

logger = logging.getLogger(__name__)

# ── Tuning knobs ─────────────────────────────────────────────────────────────
# Lower concurrency = fewer quota conflicts = fewer timeouts.
# Raise _MAX_CONCURRENT only if your Vertex AI QPM limit supports it.
_MAX_CONCURRENT  = 5    # max simultaneous data-science agent calls (7 and 10 both caused quota retries that slowed total time)
_CALL_TIMEOUT    = 600  # seconds per individual agent call
_MAX_RETRIES     = 3    # attempts per prompt before giving up
_BACKOFF_BASE    = 5    # seconds; doubles each retry (5 → 10 → 20 s) — gives Vertex AI quota time to recover between retries

_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """Lazily create the semaphore inside the running event loop."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
    return _semaphore


# ── Single-prompt executor with per-call retry + backoff ────────────────────

async def agent_call(question: str, tool_context: ToolContext) -> dict:
    """Run one data-science agent call.

    Retries up to _MAX_RETRIES times with exponential backoff so transient
    quota / timeout errors don't cascade into the outer retry pass.
    Keeping retries here (not in the caller) means the semaphore stays
    acquired during backoff — preventing a thundering-herd of retries from
    all firing at once when quota is tight.
    """
    agent_tool = AgentTool(agent=root_agent)
    last_err: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            result = await asyncio.wait_for(
                agent_tool.run_async(
                    args={"request": question},
                    tool_context=tool_context,
                ),
                timeout=_CALL_TIMEOUT,
            )
            if attempt > 1:
                logger.info("Succeeded on attempt %d | %.80s", attempt, question)
            return {"question": question, "result": result, "success": True}

        except asyncio.TimeoutError as e:
            last_err = e
            logger.warning(
                "Attempt %d/%d TIMEOUT (%.0fs) | %.80s",
                attempt, _MAX_RETRIES, _CALL_TIMEOUT, question,
            )
        except Exception as e:
            last_err = e
            logger.warning(
                "Attempt %d/%d FAILED | %s | %r | %.80s",
                attempt, _MAX_RETRIES, type(e).__name__, e, question,
            )

        if attempt < _MAX_RETRIES:
            # Jitter spreads concurrent retries so they don't all hit Vertex AI
            # at the same instant (thundering herd → more 429s → more retries).
            base_wait = _BACKOFF_BASE * (2 ** (attempt - 1))  # 2 s, 4 s
            wait = base_wait + random.uniform(0, base_wait)   # up to 2x with jitter
            logger.info("Backoff %.1f s before retry %d…", wait, attempt + 1)
            await asyncio.sleep(wait)

    logger.error(
        "All %d attempts exhausted | %s | %r | %.80s",
        _MAX_RETRIES, type(last_err).__name__, last_err, question,
    )
    return {"question": question, "result": None, "success": False}


async def _guarded_call(question: str, tool_context: ToolContext) -> dict:
    """Semaphore-limited wrapper — holds the slot across retries intentionally."""
    async with _get_semaphore():
        return await agent_call(question, tool_context)


# ── Prompt executor ──────────────────────────────────────────────────────────

async def call_db_ds_agent(tool_context: ToolContext):
    """Execute all prompts concurrently (semaphore-capped, 3 retries each).

    Each prompt runs inside _guarded_call which holds the semaphore slot
    across its own retries, preventing a surge of re-queued calls from
    overwhelming Vertex AI quota when multiple prompts fail simultaneously.
    """
    logger.info(
        "call_db_ds_agent | session=%s",
        tool_context._invocation_context.session.id,
    )

    question_list = tool_context.state.get("prompt_generator_out", [])
    flat_prompts = [
        prompt
        for section in question_list
        for prompt in section.get("prompts", [])
    ]

    if not flat_prompts:
        logger.warning("No prompts in prompt_generator_out; skipping.")
        tool_context.state["db_ds_agent_output"] = []
        return "Executed Successfully (no prompts)"

    logger.info(
        "Executing %d prompt(s), max %d concurrent, %d retries each, timeout %ds",
        len(flat_prompts), _MAX_CONCURRENT, _MAX_RETRIES, _CALL_TIMEOUT,
    )
    t0 = time.perf_counter()

    results: list[dict] = list(
        await asyncio.gather(*[_guarded_call(q, tool_context) for q in flat_prompts])
    )

    n_failed = sum(1 for r in results if not r["success"] or not r["result"])
    n_ok = len(results) - n_failed
    logger.info(
        "Done in %.1f s | %d succeeded | %d failed after %d retries each",
        time.perf_counter() - t0,
        n_ok,
        n_failed,
        _MAX_RETRIES,
    )

    if n_ok == 0:
        raise RuntimeError(
            f"All {len(results)} DB/DS agent calls failed after {_MAX_RETRIES} retries each. "
            "Check Vertex AI quota (429s) or data-science agent logs. "
            "Pipeline cannot continue without any data."
        )

    tool_context.state["db_ds_agent_output"] = [r["result"] for r in results]
    return "Executed Successfully"


# ── Partially-parallel analysis pipeline ────────────────────────────────────
#
# Dependency graph:
#   campaign_analysis  ──┬──► recommendation ──► executive_summary
#   campaign_comparison ─┘
#
#   Phase 1 (parallel):   campaign_analysis ‖ campaign_comparison
#   Phase 2 (sequential): recommendation        (needs phase-1 outputs)
#   Phase 3 (sequential): executive_summary     (needs phase-1 + phase-2 outputs)

async def Sequential_Agent(tool_context: ToolContext):
    """Run analysis sub-agents in dependency order with true Phase 1 parallelism.

    Calls tool functions directly instead of via AgentTool → LlmAgent, saving
    4 extra Gemini round-trips (one per sub-agent).  Each Gemini call inside
    the tools now runs in a thread (asyncio.to_thread), so Phase 1's
    asyncio.gather achieves genuine concurrency.

    Dependency graph:
      campaign_analysis  ──┬──► recommendation ──► executive_summary
      campaign_comparison ─┘

    Phase 1 (parallel):   campaign_analysis ‖ campaign_comparison
    Phase 2 (sequential): recommendation        (needs Phase 1 outputs)
    Phase 3 (sequential): executive_summary     (needs Phase 1 + Phase 2 outputs)
    """
    t0 = time.perf_counter()

    # Phase 1: truly parallel — both read state["db_ds_agent_output"] directly
    logger.info("Sequential_Agent Phase 1: analysis ‖ comparison [direct, concurrent]")
    await asyncio.gather(
        campaign_analysis_agent(tool_context=tool_context),
        campaign_comparison_agent(tool_context=tool_context),
    )
    logger.info("Phase 1 done in %.1f s", time.perf_counter() - t0)

    # Phase 2: reads {campaign_analysis_output, campaign_comparison_output} from state
    logger.info("Sequential_Agent Phase 2: recommendation")
    t1 = time.perf_counter()
    await recommendation_agent(tool_context=tool_context)
    logger.info("Phase 2 done in %.1f s", time.perf_counter() - t1)

    # Phase 3: reads {analysis, comparison, recommendation} from state
    logger.info("Sequential_Agent Phase 3: executive summary")
    t2 = time.perf_counter()
    await executive_summary_agent(tool_context=tool_context)
    logger.info("Phase 3 done in %.1f s", time.perf_counter() - t2)

    tool_context.state["Sequential_agent_output"] = tool_context.state.get(
        "executive_summary_output", ""
    )
    logger.info("Sequential_Agent total: %.1f s", time.perf_counter() - t0)
    return "Executed Successfully"
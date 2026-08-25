import os
import time
import logging

# Inject OS (Windows) trust store so corporate-proxy self-signed certs are trusted.
# Must run before any network/SSL import.
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

from google.genai import types
from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from .subagents.prompt_generator_list.agent import root_agent as prompt_generator
from .subagents.prompt_executor.agent import root_agent as prompt_executor
# from .subagents.data_science.agent import root_agent as db_ds_multiagent  # not used in SequentialAgent below
from .subagents.report_generation.agent import root_agent as report_generator
from .prompts import return_instructions_root
import sys

import certifi

import contextvars  # Add this for debugging

logger = logging.getLogger(__name__)

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


def setup_before_agent_call(callback_context: CallbackContext):
    """Record pipeline start time and set up initial state."""
    t0 = time.perf_counter()
    callback_context.state['pipeline_start_perf'] = t0
    callback_context.state['pipeline_start_wall'] = time.strftime('%Y-%m-%d %H:%M:%S')
    logger.info("=" * 70)
    logger.info("PIPELINE START | %s", callback_context.state['pipeline_start_wall'])
    logger.info("=" * 70)

    # Debug: Inspect current context
    ctx = contextvars.copy_context()
    var_names = [var.name for var in ctx]
    print(f"[DEBUG] Context var names: {var_names}")
    if 'current_context' in var_names:
        for var in ctx:
            if var.name == 'current_context':
                print(f"[DEBUG] 'current_context' value: {ctx[var]}")
                break
    else:
        print("[DEBUG] 'current_context' not in current context")

    user_message = callback_context.user_content.parts[0]
    if user_message.text:
        original_prompt = user_message.text
        callback_context.state['user_query'] = original_prompt


def pipeline_after_agent_call(callback_context: CallbackContext):
    """Print a full pipeline timing breakdown at the end of every run."""
    now = time.perf_counter()
    t0   = callback_context.state.get('pipeline_start_perf', now)
    t1   = callback_context.state.get('stage1_end_perf', None)   # prompt_generator done
    t2   = callback_context.state.get('stage2_end_perf', None)   # prompt_executor done
    t3   = callback_context.state.get('stage3_end_perf', now)    # report_generation done

    total   = t3 - t0
    stage1  = (t1 - t0)      if t1 else None
    stage2  = (t2 - t1)      if (t1 and t2) else None
    stage3  = (t3 - t2)      if t2 else None

    def fmt(secs):
        if secs is None:
            return "  N/A"
        m, s = divmod(secs, 60)
        return f"{int(m):2d}m {s:05.2f}s" if m else f"    {s:05.2f}s"

    sep = "=" * 70
    lines = [
        sep,
        f"PIPELINE COMPLETE | Started: {callback_context.state.get('pipeline_start_wall', '?')} | Ended: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "-" * 70,
        f"  Stage 1 — Prompt Generation  : {fmt(stage1)}",
        f"  Stage 2 — Prompt Execution   : {fmt(stage2)}",
        f"  Stage 3 — Report Generation  : {fmt(stage3)}",
        "-" * 70,
        f"  TOTAL PIPELINE TIME          : {fmt(total)}",
        sep,
    ]
    for line in lines:
        logger.info(line)
        print(line)


root_agent = SequentialAgent(
    name="Coordinator",
    sub_agents=[
        prompt_generator,
        prompt_executor,
        report_generator,
    ],
    before_agent_callback=setup_before_agent_call,
    after_agent_callback=pipeline_after_agent_call,
)
import datetime
import json
import logging

_logger = logging.getLogger(__name__)

def log_db_agent(question, tool_context, db_agent_output):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = {
        "timestamp": ts,
        "question": question,
        "tool_called": tool_context.state.get("tool_called"),
        "config_used": tool_context.state.get("config_used"),
        "sql_query": tool_context.state.get("sql_query"),
        "sql_method": tool_context.state.get("SQL Method DC/QP"),
        "sql_before_transpile": tool_context.state.get("sql_query_before_transpile"),
        "sql_after_transpile": tool_context.state.get("sql_query_after_transpile"),
    }
    try:
        output_str = json.dumps(db_agent_output, ensure_ascii=False)
    except Exception:
        output_str = str(db_agent_output)
    _logger.info("[db_agent_log] %s | output=%s", json.dumps(record), output_str[:500])
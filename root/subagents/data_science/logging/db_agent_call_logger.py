# db_logger.py
import datetime
import json

def log_db_agent(question, tool_context, db_agent_output):
    # Date-based filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d")
    log_file = f"debug_log_db_agent_{timestamp}.txt"

    with open(log_file, "a", encoding="utf-8") as f:
        # Timestamp of this entry
        f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
        f.write(f"question: {question}\n")
        f.write("----" * 10 + "\n")

        # Write only if key exists in tool_context.state
        for key, label in [
            ("tool_called", "tool_called"),
            ("config_used", "config_used"),
            ("sql_query", "sql_query"),
            ("SQL Method DC/QP", "SQL Method DC/QP"),
            ("sql_query_before_transpile", "sql_query_before_transpile"),
            ("sql_query_after_transpile", "sql_query_after_transpile"),
        ]:
            value = tool_context.state.get(key)
            if value is not None:
                f.write(f"{label}: {value}\n")
            f.write("----" * 10 + "\n")

        # Pretty-print JSON dict
        f.write("db_agent_output:\n")
        try:
            f.write(json.dumps(db_agent_output, indent=4, ensure_ascii=False) + "\n")
        except Exception:
            f.write(str(db_agent_output) + "\n")  # fallback if not serializable

        f.write("====" * 100 + "\n")

from typing import Any, Dict
from google.adk.tools import ToolContext



# Utility Functions
def tool_success(key: str, result: Any) -> Dict[str, Any]:
    return {"status": "success", key: result}

def tool_error(message: str) -> Dict[str, Any]:
    return {"status": "error", "error_message": message}

# State Keys
PERCEIVED_QUERY = "perceived_query"
FINAL_CONFIRMED_QUERY = "final_confirmed_query"
QUERY_WAS_ENHANCED = "query_was_enhanced"

# Tools
#Marks that the agent has entered the clarification phase — meaning the initial user query was vague.

def mark_clarification(tool_context: ToolContext):
    tool_context.state[QUERY_WAS_ENHANCED] = True
    return tool_success(
        "clarification_marked",
        {"message": "Clarification phase started — auto approval disabled."},
    )

#Once the agent believes it fully understands the user’s intent ,
# it calls this to save that understanding before proceeding to approval.
def set_perceived_query(perceived_query: str, tool_context: ToolContext):
    query_data = {"perceived_query": perceived_query}
    tool_context.state[PERCEIVED_QUERY] = query_data
    return tool_success(
        PERCEIVED_QUERY,
        {
            "message": None,
            "query": perceived_query
        },
    )



#Finalizes the query after user confirmation — i.e., the user agrees that the agent’s understanding is correct.
def approve_query(tool_context: ToolContext):
    if PERCEIVED_QUERY not in tool_context.state:
        return tool_error("No perceived_query found. Please set a perceived query first.")

    tool_context.state[FINAL_CONFIRMED_QUERY] = tool_context.state[PERCEIVED_QUERY]
    final_query = tool_context.state[FINAL_CONFIRMED_QUERY]["perceived_query"]

    # State update
    tool_output = tool_success(
        FINAL_CONFIRMED_QUERY,
        {
            "message": "Query approved by user.",
            "final_query": final_query,
        },
    )

    return {
        "tool_output": tool_output,
        "agent_text": f"✅ Final Query: {final_query}"  # THIS will appear in the UI
    }
#Automatically finalizes the query without asking for confirmation, only if the query was complete from the start 
# (i.e., no clarifications were needed).

def auto_approve_query(perceived_query: str, tool_context: ToolContext):
    # 🔹 Clear any old context to start fresh
    tool_context.state._data = {}

    query_data = {"perceived_query": perceived_query}
    tool_context.state[PERCEIVED_QUERY] = query_data
    tool_context.state[FINAL_CONFIRMED_QUERY] = query_data

    # State update
    tool_output = tool_success(
        FINAL_CONFIRMED_QUERY,
        {
            "message": "Query auto-approved (already complete).",
            "final_query": perceived_query,
        },
    )

    return {
        "tool_output": tool_output,
        "agent_text": f"✅ Final Query: {perceived_query}"
    }

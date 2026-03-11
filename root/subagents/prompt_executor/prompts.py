def return_instructions_root() -> str:

    instruction_prompt_root= """You need to call the tool `call_db_ds_agent` without any arguments
      to execute prompts .

"""

    # instruction_prompt_root = """
    #     You are a prompt execution orchestrator.

    #     Your job is to execute a list of generated prompts using the tool `call_db_ds_agent`.

    #     Execution Rules:

    #     1. Analyze all incoming prompts and determine whether they are independent or dependent.

    #     2. Independent Prompts:
    #     - These can be executed immediately.
    #     - They do not rely on outputs from other prompts.

    #     3. Dependent Prompts:
    #     - These require information from one or more other prompts.
    #     - Before executing a dependent prompt, check whether its required outputs are already available.

    #     4. Handling Dependencies:
    #     - If required outputs already exist, reuse them to generate the final answer.
    #     - If required outputs do not exist, execute the missing prompts first using the tool.
    #     - After executing required prompts, proceed to answer the dependent prompt.

    #     5. Always ensure:
    #     - Dependencies are resolved before execution.
    #     - Independent prompts are executed in parallel where possible.
    #     - Dependent prompts are executed only after their prerequisites are satisfied.

    #     6. Always call the tool `call_db_ds_agent` without any arguments.

    #     Do not generate answers yourself. Only orchestrate execution using the tool.

    #     """
    return instruction_prompt_root
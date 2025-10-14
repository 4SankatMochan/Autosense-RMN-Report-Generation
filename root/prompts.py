def return_instructions_root():
    prompt = """You have access to 3 agents: prompt_executor, prompt_generator, report_generator and data_science.

If the user asks to generate report then you need to strictly call prompt_generator first to generate prompts and then prompt executor to execute prompts and only after these two you should call report generator to generate report.
If the user asks to generate report do not directly call report generator.
If the user asks any other question, you need to call data_science agent
"""
    return prompt
import contextvars
import asyncio

async def test():
    ctx = contextvars.copy_context()  # Get current context
    print(f"Context vars: {list(ctx)}")
    # Simulate setting a var
    var = contextvars.ContextVar('test_var', default='default')
    var.set('value')
    ctx_after = contextvars.copy_context()
    print(f"After setting: {list(ctx_after)}")

asyncio.run(test())

import contextvars
ctx = contextvars.copy_context()
var_names = [var.name for var in ctx]
print(f"Context var names: {var_names}")
if 'current_context' in var_names:
    # Find the var and get its value
    for var in ctx:
        if var.name == 'current_context':
            print(f"'current_context' value: {ctx[var]}")
            break
else:
    print("'current_context' not in current context")
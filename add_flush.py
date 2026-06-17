import re

with open('v2x_simulation.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all print(...) statements that don't have flush=True
# Pattern matches print(...) with optional arguments, not ending with flush=...
def add_flush(match):
    print_stmt = match.group(0)
    if 'flush=' in print_stmt:
        return print_stmt  # already has flush
    
    # Check if there are arguments after the last one
    if print_stmt.endswith(')'):
        if ',' in print_stmt:
            # Has multiple arguments, add flush=True at end
            return print_stmt[:-1] + ', flush=True)'
        else:
            # Single argument, add flush=True
            return print_stmt[:-1] + ', flush=True)'
    return print_stmt

# Use regex to replace all print statements
# Pattern: print\(.*?\) - matches non-greedily
new_content = re.sub(r'print\(.*?\)', add_flush, content, flags=re.DOTALL)

with open('v2x_simulation.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Done! Added flush=True to all print() statements!")

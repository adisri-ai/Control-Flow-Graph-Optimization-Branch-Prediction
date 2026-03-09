import random
import csv

def _rand_var():
    """Return a random single-letter variable name."""
    return random.choice([chr(c) for c in range(ord("a"), ord("z") + 1)])


def _assign_statement(known_vars):
    """Generate an assignment: 'a = 1', 'a = b + 1', or 'a = b + c'"""
    var = _rand_var()

    # 33% chance for each assignment type
    choice = random.random()

    if not known_vars or choice < 0.33:
        # Simple assignment: a = 5
        val = random.randint(0, 10)
        return f"{var} = {val}", var
    elif len(known_vars) >= 1 and choice < 0.66:
        # Single source: a = b + 1
        src = random.choice(known_vars)
        op = random.choice(["+", "-", "*", "/", "%"])
        val = random.randint(1, 10)  # Avoid 0 for division
        return f"{var} = {src} {op} {val}", var
    elif len(known_vars) >= 2:
        # Two sources: a = b + c
        src1, src2 = random.sample(known_vars, 2)
        op = random.choice(["+", "-", "*", "/", "%"])
        return f"{var} = {src1} {op} {src2}", var
    else:
        # Fallback to simple assignment if not enough vars
        val = random.randint(0, 10)
        return f"{var} = {val}", var


def _generate_code_block(known_vars, nesting_level, max_nesting=3, max_statements=3):
    """
    Recursively generates a block of code (assignments, if-chains, for-loops).
    This is the core function to create nested structures.
    Returns: (list_of_code_lines, list_of_labels, list_of_new_vars)
    """
    if nesting_level > max_nesting:
        # Base case: At max depth, just return a single assignment
        stmt, new_var = _assign_statement(known_vars)
        return [stmt], [], [new_var]

    code_lines = []
    labels = []
    new_vars = []

    num_statements = random.randint(1, max_statements)

    for _ in range(num_statements):
        # Update known_vars for subsequent statements in this block
        current_known = list(set(known_vars + new_vars))

        # 70% chance of control structure, 30% of simple assignment
        # At nesting_level 0, prefer control structures
        if (nesting_level == 0 or random.random() < 0.7) and current_known:
            choice = random.choice(["if", "for"])
        else:
            choice = "assign"

        if choice == "if":
            # Generate an if-else-if-else chain
            block_str, block_labels, block_vars = _if_block_chain(
                current_known, nesting_level, max_nesting
            )
            code_lines.append(block_str)
            labels.extend(block_labels)
            new_vars.extend(block_vars)

        elif choice == "for":
            # Generate a for loop
            block_str, block_labels, block_vars = _for_loop(
                current_known, nesting_level, max_nesting
            )
            code_lines.append(block_str)
            labels.extend(block_labels)
            new_vars.extend(block_vars)

        else:  # 'assign' or fallback
            stmt, new_var = _assign_statement(current_known)
            code_lines.append(stmt)
            new_vars.append(new_var)

    return code_lines, labels, new_vars


def _if_block_chain(known_vars, nesting_level, max_nesting):
    """Generate a random if-else-if-else block chain with nested bodies."""

    # Create a variable to test
    var = random.choice(known_vars)
    val = random.randint(0, 10)
    pre = [f"{var} = {val}"]  # Set the var to a known value

    chain_len = random.randint(1, 2)  # Shorter chains, deeper nesting
    parts = []
    labels = []
    all_new_vars = []

    indent = "  " * nesting_level

    for i in range(chain_len):
        c = random.randint(0, 5)
        op = random.choice(["<", ">", "==", "<=", ">="])
        cond_str = f"if({var} {op} {c})" if i == 0 else f"else if({var} {op} {c})"

        # Evaluate this condition
        condition_met = eval(f"{val} {op} {c}")

        # Check if this branch can be taken
        is_taken = False
        if not labels or sum(labels) == 0:  # If no prior branch taken
            labels.append(1 if condition_met else 0)
            is_taken = condition_met
        else:
            labels.append(0)  # Cannot enter if a previous branch was taken

        # --- NESTED CALL ---
        # Generate the body by recursively calling _generate_code_block
        body_lines, body_labels, body_vars = _generate_code_block(
            known_vars, nesting_level + 1, max_nesting
        )

        # Add labels from the body *only if this branch was taken*
        if is_taken:
            labels.extend(body_labels)
        all_new_vars.extend(body_vars)

        # Format body with indentation
        formatted_body = "\n".join([f"{indent}  {line}" for line in body_lines])
        parts.append(f"{indent}{cond_str} {{\n{formatted_body}\n{indent}}}")

    # Add a final 'else' block (50% chance)
    if random.random() < 0.5:
        is_taken = False
        if sum(labels) == 0:  # Only enter 'else' if no 'if' was met
            labels.append(1)
            is_taken = True
        else:
            labels.append(0)

        # --- NESTED CALL ---
        body_lines, body_labels, body_vars = _generate_code_block(
            known_vars, nesting_level + 1, max_nesting
        )

        if is_taken:
            labels.extend(body_labels)
        all_new_vars.extend(body_vars)

        formatted_body = "\n".join([f"{indent}  {line}" for line in body_lines])
        parts.append(f"{indent}else {{\n{formatted_body}\n{indent}}}")

    # Combine prefix and parts
    full_code = "\n".join(pre) + "\n" + "\n".join(parts)
    return full_code, labels, all_new_vars


def _for_loop(known_vars, nesting_level, max_nesting):
    """Generate a for-loop with a nested body."""
    loop_var = "i"  # Keep it simple
    iters = random.choice([0, 1, 3])  # Test 0, 1, and N iterations
    cond_str = f"for(int {loop_var}=0; {loop_var}<{iters}; {loop_var}++)"

    # Label is 1 if loop runs, 0 if it doesn't
    label = [1] if iters > 0 else [0]
    labels = list(label)  # Create a new list for labels

    # Vars known inside the loop include the loop var
    loop_known_vars = list(set(known_vars + [loop_var]))
    indent = "  " * nesting_level

    # --- NESTED CALL ---
    body_lines, body_labels, body_vars = _generate_code_block(
        loop_known_vars, nesting_level + 1, max_nesting, max_statements=1
    )  # Keep loop bodies simpler

    # Add labels from the body *only if loop runs*
    if iters > 0:
        # If loop runs N times, body labels are repeated N times.
        # For simplicity, we'll add them once (as if it runs once),
        # which matches the "label-per-branch-taken" logic.
        labels.extend(body_labels)

    formatted_body = "\n".join([f"{indent}  {line}" for line in body_lines])

    full_code = f"{indent}{cond_str} {{\n{formatted_body}\n{indent}}}"
    return full_code, labels, body_vars


def generate_code_snippet():
    """Generates a single complex code snippet and its ground-truth labels."""

    # Start with 1-2 simple assignments to seed the 'known_vars'
    code_parts = []
    known_vars = []
    for _ in range(random.randint(1, 2)):
        stmt, new_var = _assign_statement(known_vars)
        code_parts.append(stmt)
        known_vars.append(new_var)
        known_vars = list(set(known_vars))

    # Generate the main body of the code recursively
    body_lines, body_labels, _ = _generate_code_block(
        known_vars,
        nesting_level=0,
        max_nesting=random.randint(2, 3),  # Randomize max depth
        max_statements=random.randint(2, 4),  # Randomize num of blocks
    )

    code_parts.extend(body_lines)

    # Add a final assignment
    code_parts.append(_assign_statement(known_vars)[0])
    code_parts.append("END")

    return "\n".join(code_parts), body_labels

# Testing
# --- Main script ---
if __name__ == "__main__":
    print("--- Testing Code Generator ---")
    code, labels = generate_code_snippet()
    print("\n--- Generated Code ---")
    print(code)
    print("\n--- Generated Labels ---")
    print(labels)
    print("\nGenerator test complete. You can now import this file in app.py")
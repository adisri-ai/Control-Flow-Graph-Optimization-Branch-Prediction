import re
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from tensorflow.keras.preprocessing.sequence import pad_sequences
# Note: The model and tokenizer objects are passed as arguments,
# so we don't need to import all of tensorflow here.

# -----------------------------
# --- CFG builder (Helper for Prediction)
# -----------------------------

def build_cfg(code_str: str) -> Tuple[Dict[int, str], Dict[int, List[int]]]:
    """
    Build a simple control-flow-graph (CFG) from a C++-like code string.
    Returns (node_dict, edges) where node_dict[i] = node_text and edges is
    adjacency list mapping from node index -> list of indices.
    (This is the version required by the prediction logic).
    """
    lines = [ln.strip() for ln in code_str.splitlines() if ln.strip() != ""]

    items = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        # --- if/else-if/else chain
        if ln.startswith("if(") or ln.startswith("else if(") or ln.startswith("else"):
            conds, bodies, has_else = [], [], False
            while i < len(lines) and (
                lines[i].startswith("if(")
                or lines[i].startswith("else if(")
                or lines[i].startswith("else")
            ):
                cur = lines[i]
                if cur.startswith("else") and not cur.startswith("else if("):
                    j = i + 1
                    if j < len(lines) and lines[j].startswith("{"):
                        j += 1
                    body = []
                    while j < len(lines) and "}" not in lines[j]:
                        body.append(lines[j])
                        j += 1
                    if j < len(lines) and "}" in lines[j]:
                        j += 1
                    bodies.append("\n".join(body) if body else "<EMPTY>")
                    has_else = True
                    i = j
                    break
                else:
                    conds.append(cur)
                    j = i + 1
                    if j < len(lines) and lines[j].startswith("{"):
                        j += 1
                    body = []
                    while j < len(lines) and "}" not in lines[j]:
                        body.append(lines[j])
                        j += 1
                    if j < len(lines) and "}" in lines[j]:
                        j += 1
                    bodies.append("\n".join(body) if body else "<EMPTY>")
                    i = j
            items.append(
                {
                    "type": "if_chain",
                    "conds": conds,
                    "bodies": bodies,
                    "has_else": has_else,
                }
            )
            continue

        # --- for loop
        if ln.startswith("for("):
            header = ln
            j = i + 1
            if j < len(lines) and lines[j].startswith("{"):
                j += 1
            body = []
            while j < len(lines) and "}" not in lines[j]:
                body.append(lines[j])
                j += 1
            if j < len(lines) and "}" in lines[j]:
                j += 1
            items.append(
                {
                    "type": "for",
                    "header": header,
                    "body": "\n".join(body) if body else "<EMPTY>",
                }
            )
            i = j
            continue

        # --- plain assignment
        items.append({"type": "assign", "text": ln})
        i += 1

    # convert items into nodes + edges
    nodes = []
    start_indices = []
    for it in items:
        start_indices.append(len(nodes))
        if it["type"] == "assign":
            nodes.append(it["text"])
        elif it["type"] == "for":
            nodes += [it["header"], it["body"]]
        elif it["type"] == "if_chain":
            for cond, body in zip(it["conds"], it["bodies"]):
                nodes += [cond, body]
            if it.get("has_else") and len(it["bodies"]) > len(it["conds"]):
                nodes.append(it["bodies"][-1])

    edges = {i: [] for i in range(len(nodes))}

    for idx, it in enumerate(items):
        start = start_indices[idx]
        exit_idx = (
            start_indices[idx + 1] if idx + 1 < len(start_indices) else len(nodes)
        )
        if it["type"] == "assign":
            if exit_idx < len(nodes):
                edges[start].append(exit_idx)
        elif it["type"] == "for":
            hdr, body = start, start + 1
            edges[hdr] = [body]
            if exit_idx < len(nodes):
                edges[hdr].append(exit_idx)
            edges[body] = [hdr]
        elif it["type"] == "if_chain":
            pairs = len(it["conds"])
            for k in range(pairs):
                cond, body = start + 2 * k, start + 2 * k + 1
                if k + 1 < pairs:
                    nxt = start + 2 * (k + 1)
                else:
                    nxt = start + 2 * pairs if it.get("has_else") else exit_idx
                edges[cond] = [body]
                if nxt < len(nodes):
                    edges[cond].append(nxt)
                if exit_idx < len(nodes):
                    edges[body].append(exit_idx)
            if it.get("has_else"):
                else_idx = start + 2 * pairs
                if exit_idx < len(nodes):
                    edges[else_idx].append(exit_idx)

    node_dict = {i: nodes[i] for i in range(len(nodes))}
    for k in edges:
        edges[k] = [x for x in edges[k] if x < len(nodes)]
    return node_dict, edges


# -----------------------------
# --- Prediction function
# -----------------------------

def predict_flow_for_code(code_str: str, model, tokenizer, meta: Dict[str, Any], prob_thresh: float = 0.5, loop_threshold: int = 3) -> List[Tuple[int, str]]:
    """
    Given a code string, build its CFG and use the trained LSTM model to
    decide whether to enter conditional/loop bodies. Returns an ordered list
    of visited nodes: list of tuples (node_index, node_text).

    Rules:
      - For each condition node (if/else if) create input string as the
        concatenation of visited nodes (same as training) and ask model.
      - If probability >= prob_thresh -> treat as 'enter' else 'skip'.
      - For for-loops: if predicted enter, iterate body up to loop_threshold times
        (safeguard) and then exit.
    """
    node_dict, edges = build_cfg(code_str)
    
    if not node_dict:
        return [] # Handle empty input
        
    nodes = [node_dict[i] for i in range(len(node_dict))]

    visited_nodes = []
    execution_path = []  # (idx, text)

    i = 0
    steps = 0
    max_steps = max(500, len(nodes)*10)
    while i < len(nodes) and steps < max_steps:
        steps += 1
        node = nodes[i]
        
        # condition nodes
        if node.startswith('if(') or node.startswith('else if('):
            inp_nodes = visited_nodes
            inp = ' || '.join(inp_nodes[-40:]) if inp_nodes else '<EMPTY_CONTEXT>'
            seq = tokenizer.texts_to_sequences([inp])
            padded = pad_sequences(seq, maxlen=meta.get('maxlen', 40), padding='pre')
            prob = float(model.predict(padded, verbose=0)[0,0])
            take = prob >= prob_thresh
            
            succs = edges.get(i, [])
            if take and len(succs) >= 1:
                # go into body
                body_idx = succs[0]
                execution_path.append((i, node))
                visited_nodes.append(node)
                
                if body_idx < len(nodes):
                    execution_path.append((body_idx, nodes[body_idx]))
                    visited_nodes.append(nodes[body_idx])
                
                # after body we go to exit
                next_nodes = edges.get(body_idx, [])
                if next_nodes:
                    i = next_nodes[0]
                else:
                    i = body_idx + 1 # Fallback
                continue
            else:
                # skip to next node as per CFG (second successor)
                execution_path.append((i, node + f"  # predicted_skip(prob={prob:.3f})"))
                visited_nodes.append(node)
                
                if len(succs) >= 2:
                    i = succs[1]
                else:
                    # No 'else' branch, find the next node after the body
                    body_idx = succs[0] if succs else i + 1
                    next_nodes = edges.get(body_idx, [])
                    if next_nodes:
                        i = next_nodes[0]
                    else:
                        i = body_idx + 1 # Fallback
                continue

        # else node (this is the body of the 'else')
        if node.strip().startswith('else') or node.startswith('else'):
            inp_nodes = visited_nodes
            inp = ' || '.join(inp_nodes[-40:]) if inp_nodes else '<EMPTY_CONTEXT>'
            seq = tokenizer.texts_to_sequences([inp])
            padded = pad_sequences(seq, maxlen=meta.get('maxlen', 40), padding='pre')
            prob = float(model.predict(padded, verbose=0)[0,0])

            if prob >= prob_thresh:
                # ENTER else body
                execution_path.append((i, node))
                visited_nodes.append(node)
                succs = edges.get(i, [])
                if succs:
                    i = succs[0]
                else:
                    i += 1
                continue
            else:
                # SKIP else body
                execution_path.append((i, node + f"  # predicted_skip_else(prob={prob:.3f})"))
                visited_nodes.append(node)
                succs = edges.get(i, [])
                if succs:
                    i = succs[0]
                else:
                    i += 1
                continue


        # for-loops
        if node.startswith('for('):
            inp_nodes = visited_nodes
            inp = ' || '.join(inp_nodes[-40:]) if inp_nodes else '<EMPTY_CONTEXT>'
            seq = tokenizer.texts_to_sequences([inp])
            padded = pad_sequences(seq, maxlen=meta.get('maxlen', 40), padding='pre')
            prob = float(model.predict(padded, verbose=0)[0,0])
            succs = edges.get(i, [])
            enter = prob >= prob_thresh
            
            if enter and len(succs) >= 1:
                body_idx = succs[0]
                # simulate loop with threshold
                iterations = 0
                while iterations < loop_threshold:
                    execution_path.append((i, node + f"  # loop_iter({iterations})"))
                    visited_nodes.append(node)
                    
                    if body_idx < len(nodes):
                        execution_path.append((body_idx, nodes[body_idx]))
                        visited_nodes.append(nodes[body_idx])
                    iterations += 1
                    
                # after threshold exit to successor after header
                if len(succs) >= 2:
                    i = succs[1]
                else:
                    i = body_idx + 1 # Fallback
                continue
            else:
                # skip loop
                execution_path.append((i, node + f"  # predicted_skip_loop(prob={prob:.3f})"))
                visited_nodes.append(node)
                # move to exit successor if present
                if len(succs) >= 2:
                    i = succs[1]
                else:
                    i += 1 # Fallback
                continue

        # plain assignment or body
        execution_path.append((i, node))
        visited_nodes.append(node)
        # default move to next via edges or linear index
        succs = edges.get(i, [])
        if succs:
            i = succs[0]
        else:
            i += 1
            
    return execution_path
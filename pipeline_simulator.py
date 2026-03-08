import re
import pandas as pd


# --------------------------
# Helper: parse variables
# --------------------------
def parse_vars(instr):
    """
    Parses an instruction string to find its destination and source registers.
    Returns: ([dest], [src1, src2, ...])
    """
    if not instr or instr.startswith("<"):
        return [], []

    # Regex for assignment: 'dest = src1 op src2' or 'dest = src1'
    assign = re.match(r"^\s*([a-zA-Z_]\w*)\s*=\s*(.+)$", instr)
    if assign:
        dest = assign.group(1)
        # Find all variables in the source expression
        srcs = re.findall(r"\b[a-zA-Z_]\w*\b", assign.group(2))
        # Filter out cases like 'a = a + 1' where dest is also a src
        srcs = [v for v in srcs if v != dest]
        return [dest], list(set(srcs))  # Return unique sources
    else:
        # For non-assignment (e.g., branches), all vars are sources
        srcs = re.findall(r"\b[a-zA-Z_]\w*\b", instr)
        return [], list(set(srcs))  # Return unique sources


# --------------------------
# 5-Stage Pipeline Simulator
# --------------------------
def simulate_pipeline_table(instructions, truth=None, pred=None, flush_penalty=2):
    """
    Simulates a 5-stage (F,D,E,M,W) pipeline.
    Handles RAW data hazards by stalling.
    Handles branch mispredictions by flushing.
    """
    stages = ["F", "D", "E", "M", "W"]
    pipeline = {s: None for s in stages}
    instr_idx = 0
    cycle_num = 0
    history = []
    stalls = 0
    flushes = 0
    hazard_info = {}  # Store hazard info per cycle

    # Pad instructions to let pipeline drain
    instructions_padded = instructions + [None] * (len(stages) - 1)

    while True:
        cycle_num += 1
        # Create a snapshot of the pipeline *before* this cycle's shifts
        current_cycle_state = pipeline.copy()
        history.append(current_cycle_state)

        # --- 1. Check for pipeline empty ---
        # MODIFIED: Only break if pipeline is empty AND all instructions are fetched
        if all(v is None for v in pipeline.values()) and instr_idx >= len(
            instructions_padded
        ):
            break  # Pipeline is empty and all instructions processed

        # --- 2. Handle W-Stage (Writeback) ---
        pipeline["W"] = None  # Clear W stage first (result is "written")
        if pipeline["M"] and not pipeline["M"].startswith("<"):
            pipeline["W"] = pipeline["M"]

        # --- 3. Handle M-Stage (Memory) ---
        pipeline["M"] = None
        if pipeline["E"] and not pipeline["E"].startswith("<"):
            pipeline["M"] = pipeline["E"]
        elif pipeline["E"] == "<FLUSH>":
            pipeline["M"] = "<FLUSH>"

        # --- 4. Handle E-Stage (Execute) ---
        pipeline["E"] = None
        branch_flush = False

        # Check for branch instruction in D stage (was E, moved to D for earlier flush)
        if pipeline["D"] and (
            pipeline["D"].startswith("if(") or pipeline["D"].startswith("for(")
        ):
            if truth is not None and pred is not None:
                # Find the corresponding branch decision
                try:
                    branch_idx = instructions.index(pipeline["D"])
                    if branch_idx in truth and branch_idx in pred:
                        if truth[branch_idx] != pred[branch_idx]:
                            # Misprediction!
                            branch_flush = True
                            flushes += flush_penalty
                            hazard_info[cycle_num] = (
                                f"Branch Mispredict: Flush F, D. ({flush_penalty} cycle penalty)"
                            )
                            # Flush F and D stages
                            pipeline["F"] = None
                            pipeline["D"] = "<FLUSH>"
                            pipeline["E"] = "<FLUSH>"  # Propagate flush
                            # Simulate penalty by doing nothing for 'flush_penalty' cycles
                            for _ in range(flush_penalty):
                                history.append(
                                    {
                                        s: ("<FLUSH>" if s in ("D", "E") else "---")
                                        for s in stages
                                    }
                                )
                            cycle_num += flush_penalty
                except ValueError:
                    # Instruction not in list, this can happen if paths diverge
                    pass

        # --- 5. Handle D-Stage (Decode / Hazard Check) ---
        if pipeline["D"] and not pipeline["D"].startswith("<") and not branch_flush:

            # Get dest/srcs for instruction in D stage
            d_dest_list, d_srcs = parse_vars(pipeline["D"])

            # Get destinations for instructions in E and M stages
            prev_e_dest_list, _ = (
                parse_vars(pipeline["E"]) if pipeline["E"] else ([], [])
            )
            prev_e_dest = prev_e_dest_list[0] if prev_e_dest_list else None

            prev_m_dest_list, _ = (
                parse_vars(pipeline["M"]) if pipeline["M"] else ([], [])
            )
            prev_m_dest = prev_m_dest_list[0] if prev_m_dest_list else None

            # --- Hazard Detection ---
            # Check for Read-After-Write (RAW) data hazard.
            # This is the only hazard that requires a stall in this simple in-order pipeline.
            # We stall if this instruction (in D) READS a register that a
            # previous instruction (in E or M) WRITES to.

            stall = False
            if prev_e_dest and prev_e_dest in d_srcs:
                # RAW Hazard: Instr(D) needs result from Instr(E)
                stall = True
                hazard_info[cycle_num] = (
                    f"RAW Hazard: Stall. {pipeline["D"]} needs {prev_e_dest} from {pipeline["E"]}."
                )
            elif prev_m_dest and prev_m_dest in d_srcs:
                # RAW Hazard: Instr(D) needs result from Instr(M)
                stall = True
                hazard_info[cycle_num] = (
                    f"RAW Hazard: Stall. {pipeline["D"]} needs {prev_m_dest} from {pipeline["M"]}."
                )

            # --- WAW & WAR Hazards ---
            # Write-After-Write (WAW) and Write-After-Read (WAR) hazards
            # are structurally avoided in this simple 5-stage in-order pipeline.
            # - WAR: Reads happen in stage D/E, Writes happen *much later* in stage W.
            #   An instruction will always read its operands *before* a later
            #   instruction can write to them. No stall needed.
            # - WAW: All writes happen in the W stage, in program order.
            #   The correct value will always be the one from the latest instruction.
            #   No stall needed.

            if not stall:
                pipeline["E"] = pipeline["D"]  # Advance D -> E
                pipeline["D"] = None
            else:
                # Stall: keep D and F stages as-is, inject bubble into E
                pipeline["E"] = "<STALL>"
                stalls += 1

        elif pipeline["D"] == "<FLUSH>":
            pipeline["E"] = "<FLUSH>"  # Propagate flush
            pipeline["D"] = None

        # --- 6. Handle F-Stage (Fetch) ---
        if (
            pipeline["F"]
            and not pipeline["F"].startswith("<")
            and pipeline["D"] is None
        ):
            pipeline["D"] = pipeline["F"]
            pipeline["F"] = None

        # --- 7. Fetch next instruction ---
        if (
            pipeline["F"] is None
            and instr_idx < len(instructions_padded)
            and not branch_flush
        ):
            pipeline["F"] = instructions_padded[instr_idx]
            instr_idx += 1

    # --- 8. Format results ---
    df = pd.DataFrame(history)
    # Handle empty history
    if df.empty:
        return df, 0, (0, 0)
    df.index = range(1, len(df) + 1)
    df.index.name = "Cycle"
    # Add hazard info column
    df["Events"] = df.index.map(hazard_info).fillna("")
    return df, cycle_num - 1, (stalls, flushes)
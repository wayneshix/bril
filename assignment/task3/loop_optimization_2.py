from copy import deepcopy
from collections import OrderedDict
import click
import sys
import json

from cfg import form_cfg_w_blocks, join_cfg, INSTRS
from reaching_definitions import reaching_defs_func
from dominator_utilities import get_natural_loops, build_dominance_tree
from bril_core_utilities import has_side_effects, is_label, is_jmp, is_br
from bril_core_constants import *


LOOP_INVARIANT = True
NOT_LOOP_INVARIANT = not LOOP_INVARIANT


LOOP_PREHEADER_COUNTER = 0
NEW_LOOP_PREHEADER = "new.loop.preheader"


NEW_CFG_LABEL = "new.cfg.label"
NEW_CFG_LABEL_IDX = 0


def gen_loop_preheader():
    global LOOP_PREHEADER_COUNTER
    LOOP_PREHEADER_COUNTER += 1
    return f"{NEW_LOOP_PREHEADER}.{LOOP_PREHEADER_COUNTER}"


def insert_preheaders(natural_loops, instrs_w_blocks):
    headers = set()
    preheadermap = OrderedDict()
    backedgemap = OrderedDict()

    # Map back edges for loop headers
    for _, (A, _), header, _ in natural_loops:
        backedgemap.setdefault(header, []).append(A)

    new_instrs = []
    
    # Iterate through instructions and blocks
    for instr, instr_block in instrs_w_blocks:
        if is_label(instr):
            header = instr[LABEL]

            # Check if this label is a loop header
            for natural_loop_blocks, _, loop_header, _ in natural_loops:
                if loop_header == header and loop_header not in headers:
                    headers.add(loop_header)
                    preheader = gen_loop_preheader()
                    preheadermap[loop_header] = preheader

                    # Insert new preheader instruction
                    new_preheader_instr = {LABEL: preheader}
                    new_instrs.append((new_preheader_instr, preheader))

                    # Update labels in branch/jump instructions for non-loop blocks
                    for inner_instr, block in instrs_w_blocks:
                        if (is_br(inner_instr) or is_jmp(inner_instr)) and block not in natural_loop_blocks:
                            update_labels(inner_instr, loop_header, preheader)

                    # Update labels in the new instructions
                    for inner_instr, block in new_instrs:
                        if (is_br(inner_instr) or is_jmp(inner_instr)) and block not in preheadermap.values() and block not in natural_loop_blocks:
                            update_labels(inner_instr, loop_header, preheader)
        
        # Append the original instruction and block
        new_instrs.append((instr, instr_block))

    # Return the updated instruction sequence and preheader map
    final_instrs = [instr for instr, _ in new_instrs]
    return preheadermap, final_instrs


def update_labels(instr, old_label, new_label):
    """Helper function to update jump/branch instruction labels."""
    if old_label in instr[LABELS]:
        instr[LABELS] = [new_label if lbl == old_label else lbl for lbl in instr[LABELS]]



def identify_li_recursive(cfg, reaching_definitions, func_args, loop_blocks, basic_block, instrs_invariant_map, var_invariant_map):
    """
    Identify loop-invariant instructions recursively.
    """
    in_dict, _ = reaching_definitions

    # Convert loop_blocks to set for faster lookups
    loop_block_set = set(loop_blocks)

    for basic_block in loop_block_set:
        instrs = cfg[basic_block][INSTRS]

        for instr in instrs:
            # Check for constants
            if VALUE in instr and DEST in instr:
                handle_constant(instr, instrs_invariant_map, var_invariant_map, cfg, loop_block_set)
            # Check for instructions with arguments
            elif ARGS in instr and DEST in instr:
                dst = instr[DEST]
                args = instr[ARGS]

                if is_invariant_with_args(cfg, args, dst, in_dict, loop_block_set, func_args, var_invariant_map, instrs):
                    instrs_invariant_map[id(instr)] = LOOP_INVARIANT
                    var_invariant_map[dst] = LOOP_INVARIANT
                else:
                    instrs_invariant_map[id(instr)] = NOT_LOOP_INVARIANT
                    var_invariant_map[dst] = NOT_LOOP_INVARIANT
            else:
                instrs_invariant_map[id(instr)] = NOT_LOOP_INVARIANT

    return instrs_invariant_map, var_invariant_map


def handle_constant(instr, instrs_invariant_map, var_invariant_map, cfg, loop_block_set):
    """Handle constant instructions and mark them as loop invariant if applicable."""
    dst = instr[DEST]
    val_is_loop_invariant = True

    # Check if there are any other definitions of this constant in the loop
    for other_block in loop_block_set:
        for other_instr in cfg[other_block][INSTRS]:
            if DEST in other_instr and id(instr) != id(other_instr):
                if other_instr[DEST] == dst:
                    val_is_loop_invariant = False
                    break

    instrs_invariant_map[id(instr)] = LOOP_INVARIANT if val_is_loop_invariant else NOT_LOOP_INVARIANT
    var_invariant_map[dst] = LOOP_INVARIANT if val_is_loop_invariant else NOT_LOOP_INVARIANT


def is_invariant_with_args(cfg, args, dst, in_dict, loop_block_set, func_args, var_invariant_map, instrs):
    """Check if an instruction with arguments is loop invariant."""
    # Condition 1: Check if the arguments are defined outside the loop
    for x in args:
        if reaches_from_outside_loop(x, dst, in_dict, loop_block_set):
            continue

        # Condition 2: Check if the arguments are defined exactly once inside the entire function
        if not is_defined_once(func_args, dst, instrs, var_invariant_map, x):
            return False

    return True


def reaches_from_outside_loop(arg, dst, in_dict, loop_block_set):
    """Check if an argument reaches from outside the loop."""
    for block, defs in in_dict.items():
        if block not in loop_block_set:
            continue
        for _, var in defs:
            if var == dst:
                return False
    return True


def is_defined_once(func_args, dst, instrs, var_invariant_map, arg):
    """Check if an argument is defined exactly once and is loop invariant."""
    x_def_counter = func_args.count(dst)

    # Count definitions inside the loop
    for def_instr in instrs:
        if DEST in def_instr and def_instr[DEST] == dst:
            x_def_counter += 1

    # Check if the argument is invariant and defined exactly once
    return x_def_counter == 1 and var_invariant_map.get(arg, False)

 
################


def identify_loop_invariant_instrs(cfg, func_args, loop_blocks, loop_instrs, loop_header, reaching_definitions):
    """
    For a given loop, identify those instructions in the loop that are loop invariant.
    """
    assert loop_header in loop_blocks

    # Initialize instruction invariant map
    instrs_invariant_map = OrderedDict()
    for loop_instr, _ in loop_instrs:
        instrs_invariant_map[id(loop_instr)] = NOT_LOOP_INVARIANT

    previous_instrs_invariant_map = {}

    # Continue marking invariants until no further changes are detected
    while True:
        var_invariant_map = OrderedDict()
        for loop_instr, _ in loop_instrs:
            if DEST in loop_instr:
                var_invariant_map[loop_instr[DEST]] = NOT_LOOP_INVARIANT

        # Identify loop-invariant instructions recursively
        instrs_invariant_map, var_invariant_map = identify_li_recursive(
            cfg, reaching_definitions, func_args, loop_blocks, loop_header,
            instrs_invariant_map, var_invariant_map
        )

        # Check if there are changes by comparing with the previous iteration
        if instrs_invariant_map == previous_instrs_invariant_map:
            break  # No changes detected; exit the loop
        else:
            previous_instrs_invariant_map = instrs_invariant_map.copy()

    return instrs_invariant_map, var_invariant_map



########

def gather_nodes(node, dominator_tree, natural_loop_nodes):
    """
    Iteratively gather nodes from the dominator tree that are part of the natural loop.
    """
    nodes = []
    stack = [node]  # Initialize the stack with the starting node

    while stack:
        current_node = stack.pop()
        if current_node in natural_loop_nodes:
            nodes.append(current_node)
            stack.extend(dominator_tree[current_node])

    return nodes


def filter_loop_invariant_instrs(cfg, natural_loop, dominator_tree, loop_instrs, loop_instrs_map, id2instr):
    """
    Filter loop-invariant instructions to only those that can be moved out of the loop.
    """
    natural_loop_nodes, _, header, exits = natural_loop

    # Step 1: Filter instructions marked as loop invariant
    status_filter = [identifier for identifier, status in loop_instrs_map.items() if status]

    # Step 2: Check if the instruction dominates all uses in the loop
    dominate_filter = []
    for identifier in status_filter:
        def_instr, identifier_block = id2instr[identifier]
        dst = def_instr[DEST]

        # Check if the instruction dominates all its uses in its block
        if dominates_in_block(cfg[identifier_block][INSTRS], dst, identifier):
            # Check if the instruction dominates all uses in the loop
            dominated_blocks = set(gather_nodes(identifier_block, dominator_tree, natural_loop_nodes))
            all_loop_blocks = set(gather_nodes(header, dominator_tree, natural_loop_nodes))
            if dominates_in_loop(cfg, dst, all_loop_blocks.difference(dominated_blocks)):
                dominate_filter.append(identifier)

    # Step 3: Ensure no other definitions of the same destination variable exist in the loop
    def_filter = [identifier for identifier in dominate_filter if has_unique_definition(loop_instrs, id2instr[identifier][0])]

    # Step 4: Check if the instruction dominates all exits and is not used after the loop
    exit_filter = []
    for identifier in def_filter:
        def_instr, identifier_block = id2instr[identifier]
        if dominates_exits(cfg, def_instr, identifier_block, exits, natural_loop_nodes, dominator_tree):
            exit_filter.append(identifier)

    return exit_filter


def dominates_in_block(instrs, dst, identifier):
    """
    Check if an instruction dominates all uses of a destination variable within its own block.
    """
    position = next((i for i, instr in enumerate(instrs) if id(instr) == identifier), None)
    assert position is not None

    # The instruction dominates all uses of its destination if there are no earlier uses of the destination
    return all(i >= position for i, instr in enumerate(instrs) if ARGS in instr and dst in instr[ARGS])


def dominates_in_loop(cfg, dst, non_dominated_blocks):
    """
    Check if the destination variable is used in blocks that are not dominated by the instruction.
    """
    for block in non_dominated_blocks:
        for instr in cfg[block][INSTRS]:
            if ARGS in instr and dst in instr[ARGS]:
                return False
    return True


def has_unique_definition(loop_instrs, def_instr):
    """
    Ensure the destination variable of the given instruction is defined exactly once within the loop.
    """
    dest = def_instr[DEST]
    return sum(1 for instr, _ in loop_instrs if DEST in instr and instr[DEST] == dest) == 1


def dominates_exits(cfg, def_instr, identifier_block, exits, natural_loop_nodes, dominator_tree):
    """
    Check if the instruction dominates all loop exits and is not used after the loop.
    """
    dominated_blocks = set(gather_nodes(identifier_block, dominator_tree, natural_loop_nodes))

    # Check if the instruction dominates all exits
    for exit_block, _ in exits:
        if exit_block not in dominated_blocks:
            return False

    # Check if the variable is used after the loop
    dst = def_instr[DEST]
    for block in cfg:
        if block not in natural_loop_nodes:
            for instr in cfg[block][INSTRS]:
                if ARGS in instr and dst in instr[ARGS]:
                    return False

    # Check if the instruction has side effects
    return not has_side_effects(def_instr)


#######

def insert_into_bb(cfg, basic_block, instr):
    """
    Insert an instruction into a basic block, ensuring terminators remain at the end.
    """
    instrs = cfg[basic_block][INSTRS]
    
    if instrs and OP in instrs[-1] and instrs[-1][OP] in TERMINATORS:
        instrs.insert(-1, instr)  # Insert before the last terminator
    else:
        instrs.append(instr)  # Add to the end if no terminators

    cfg[basic_block][INSTRS] = instrs


def remove_from_bb(cfg, basic_block, identifier):
    """
    Remove an instruction from a basic block by its identifier.
    """
    cfg[basic_block][INSTRS] = [instr for instr in cfg[basic_block][INSTRS] if id(instr) != identifier]


def recursively_move_instructions(cfg, header, preheadermap, identifiers_to_move, destination, id2instr, vars_inside_loop, moved_vars):
    """
    Move instructions in an order such that argument dependencies are correct.
    """
    # Find the identifier for the instruction with the target destination
    identifier = next((curr_id for curr_id in identifiers_to_move if id2instr[curr_id][0][DEST] == destination), None)

    if identifier is None:
        return False

    instr, basic_block = id2instr[identifier]
    dst = instr[DEST]

    # Recursively ensure all arguments are moved before the instruction
    if ARGS in instr:
        for arg in instr[ARGS]:
            if arg not in moved_vars and arg in vars_inside_loop:
                if not recursively_move_instructions(cfg, header, preheadermap, identifiers_to_move, arg, id2instr, vars_inside_loop, moved_vars):
                    return False

    # Insert the current instruction into the preheader and remove it from its original block
    preheader = preheadermap[header]
    insert_into_bb(cfg, preheader, instr)
    remove_from_bb(cfg, basic_block, identifier)

    # Mark the destination as moved
    moved_vars.add(dst)
    return True
###

def move_instructions(cfg, header, preheadermap, identifiers_to_move, id2instr, vars_inside_loop, moved_vars):
    """
    Move instructions marked as loop-invariant into the preheader in dependency order.
    """
    for identifier in identifiers_to_move:
        instr, basic_block = id2instr[identifier]

        # Check if any arguments need to be moved first
        if ARGS in instr:
            if any(arg not in moved_vars and arg in vars_inside_loop for arg in instr[ARGS]):
                # If any argument inside the loop is not moved, recursively move it
                if not all(
                    recursively_move_instructions(cfg, header, preheadermap, identifiers_to_move, arg, id2instr, vars_inside_loop, moved_vars)
                    for arg in instr[ARGS] if arg in vars_inside_loop and arg not in moved_vars
                ):
                    continue  # Skip this instruction if the argument could not be moved

        dst = instr[DEST]
        if dst in moved_vars:
            continue  # Skip if the destination is already moved

        # Insert into preheader and remove from original block
        preheader = preheadermap[header]
        insert_into_bb(cfg, preheader, instr)
        remove_from_bb(cfg, basic_block, identifier)

        # Mark the destination as moved
        moved_vars.add(dst)


def loop_licm(natural_loop, cfg, func_args, preheadermap, reaching_definitions, dominance_tree):
    """
    Perform Loop Invariant Code Motion (LICM) on a given loop.
    """
    loop_blocks, _, header, _ = natural_loop

    # Gather instructions in the loop and variables defined inside the loop
    loop_instrs = [(instr, block_name) for block_name in loop_blocks for instr in cfg[block_name][INSTRS]]
    vars_inside_loop = {instr[DEST] for instr, _ in loop_instrs if DEST in instr}

    # Identify loop invariant instructions
    loop_instrs_map, _ = identify_loop_invariant_instrs(cfg, func_args, loop_blocks, loop_instrs, header, reaching_definitions)

    # Build map from identifier to instruction and block
    id2instr = {identifier: (instr, block_name) for identifier in loop_instrs_map for instr, block_name in loop_instrs if id(instr) == identifier}

    # Filter loop invariant instructions that can be moved
    identifiers_to_move = filter_loop_invariant_instrs(cfg, natural_loop, dominance_tree, loop_instrs, loop_instrs_map, id2instr)

    # Move the instructions to the preheader
    move_instructions(cfg, header, preheadermap, identifiers_to_move, id2instr, vars_inside_loop, set())

    return cfg


def func_licm(func):
    """
    Perform Loop Invariant Code Motion (LICM) on a function.
    """
    natural_loops = get_natural_loops(func)
    cfg = form_cfg_w_blocks(func)

    # Collect instructions with blocks for preheader insertion
    instrs_w_blocks = [(instr, block) for block in cfg for instr in cfg[block][INSTRS]]
    preheadermap, new_instrs = insert_preheaders(natural_loops, instrs_w_blocks)

    func[INSTRS] = new_instrs  # Update function instructions with preheaders
    cfg = form_cfg_w_blocks(func)  # Rebuild CFG after preheaders insertion

    # Perform reaching definitions and dominance analysis
    reaching_definitions = reaching_defs_func(func)
    dominance_tree, _ = build_dominance_tree(func)

    func_args = [a[NAME] for a in func.get(ARGS, [])]  # Extract function arguments

    # Apply LICM to each natural loop in the function
    for natural_loop in natural_loops:
        cfg = loop_licm(natural_loop, cfg, func_args, preheadermap, reaching_definitions, dominance_tree)

    return join_cfg(cfg)  # Rebuild and return the final CFG


def licm_main(program):
    """
    LICM wrapper function that applies LICM to all functions in the program.
    """
    for func in program["functions"]:
        func["instrs"] = func_licm(func)  # Perform LICM and update instructions
    return program


@click.command()
@click.option('--licm', default=False, help='Run Loop Invariant Code Motion.')
@click.option('--pretty-print', default=False, help='Pretty Print Before and After Optimization.')
def main(licm, pretty_print):
    prog = json.load(sys.stdin)
    if pretty_print:
        print(json.dumps(prog, indent=4, sort_keys=True))
    if licm:
        final_prog = licm_main(prog)
    else:
        final_prog = prog
    if pretty_print:
        print(json.dumps(final_prog, indent=4, sort_keys=True))
    print(json.dumps(final_prog))


if __name__ == "__main__":
    main()
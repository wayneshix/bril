import sys
import json
import logging
from collections import defaultdict, deque
from cfg import form_blocks
from cfg import flatten

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_pointer_type(typ):
    """
    Check if a type is a pointer type.
    """
    if isinstance(typ, dict):
        return typ.get('ptr', False)
    elif isinstance(typ, str):
        return typ.startswith('ptr')
    return False

def construct_cfg(blocks):
    """
    Construct a Control Flow Graph (CFG) from the given blocks.
    """
    labels = []
    block_map = {}
    for idx, block in enumerate(blocks):
        if 'label' in block[0]:
            label = block[0]['label']
        else:
            label = f'<bb{idx}>'
        labels.append(label)
        block_map[label] = block

    cfg = {label: [] for label in labels}
    for idx, block in enumerate(blocks):
        label = labels[idx]
        last_instr = block[-1] if block else None
        if last_instr and 'op' in last_instr:
            op = last_instr['op']
            if op == 'br':
                cfg[label].extend(last_instr['labels'])
            elif op == 'jmp':
                cfg[label].append(last_instr['labels'][0])
            else:
                if idx + 1 < len(blocks):
                    cfg[label].append(labels[idx + 1])
        else:
            if idx + 1 < len(blocks):
                cfg[label].append(labels[idx + 1])
    return cfg, labels

def alias_analysis(blocks, cfg, labels, func_args, alloc_sites):
    """
    Perform alias analysis to determine points-to sets for pointers.
    """
    block_map = dict(zip(labels, blocks))
    in_state = {label: {} for label in labels}
    out_state = {label: {} for label in labels}

    # Initialize the analysis state with function arguments
    init_state = {}
    for arg_name, arg_type in func_args.items():
        if is_pointer_type(arg_type):
            alloc_site = f'arg_{arg_name}'
            init_state[arg_name] = set([(alloc_site, 0)])

    worklist = deque(labels)
    while worklist:
        label = worklist.popleft()
        block = block_map[label]
        preds = [pred for pred in cfg if label in cfg[pred]]
        in_map = defaultdict(set)

        if preds:
            for pred in preds:
                for var, locs in out_state[pred].items():
                    in_map[var].update(locs)
        else:
            for var, locs in init_state.items():
                in_map[var].update(locs)

        in_state[label] = in_map.copy()
        old_out = out_state[label]
        out_map = analyze_block(block, in_map, alloc_sites)
        out_state[label] = out_map

        if out_map != old_out:
            for succ in cfg[label]:
                if succ not in worklist:
                    worklist.append(succ)
    return in_state, out_state

def analyze_block(block, in_map, alloc_sites):
    """
    Analyze a single block for aliasing information.
    """
    state = {var: locs.copy() for var, locs in in_map.items()}
    for instr in block:
        if 'op' in instr:
            op = instr['op']
            dest = instr.get('dest')
            args = instr.get('args', [])
            if op == 'alloc':
                alloc_site = alloc_sites[id(instr)]
                state[dest] = set([(alloc_site, 0)])
            elif op == 'id':
                y = args[0]
                if y in state:
                    state[dest] = state[y].copy()
                else:
                    state[dest] = set([('unknown', 0)])
            elif op in {'ptradd', 'gep'}:
                p = args[0]
                offset = args[1] if len(args) > 1 else 0
                if p in state:
                    base_points_to = state[p]
                    new_points_to = set()
                    offset_value = 0
                    if isinstance(offset, int):
                        offset_value = offset
                    elif offset.isdigit():
                        offset_value = int(offset)
                    else:
                        # Offset is not a constant; conservatively use unknown
                        new_points_to.add(('unknown', 0))
                        state[dest] = new_points_to
                        continue
                    for alloc_site, base_offset in base_points_to:
                        new_offset = base_offset + offset_value
                        new_points_to.add((alloc_site, new_offset))
                    state[dest] = new_points_to
                else:
                    state[dest] = set([('unknown', 0)])
            elif op == 'load':
                # Load from pointer; result may point to unknown
                state[dest] = set([('unknown', 0)])
            elif op == 'store':
                # Store may write to unknown memory
                pass  # No change in alias information
            elif op == 'call':
                # Function calls may return pointers
                dest_type = instr.get('type')
                if dest and is_pointer_type(dest_type):
                    state[dest] = set([('unknown', 0)])
                # Conservatively assume pointers passed as arguments may alias unknown
                for arg in args:
                    if arg in state:
                        state[arg].add(('unknown', 0))
            elif op == 'phi':
                # Phi nodes merge variables
                phi_args = instr.get('args', [])
                state[dest] = set()
                for var in phi_args:
                    if var in state:
                        state[dest].update(state[var])
                    else:
                        state[dest].add(('unknown', 0))
            elif op == 'select':
                # Select between two pointers
                true_var, false_var = args[1], args[2]
                state[dest] = set()
                if true_var in state:
                    state[dest].update(state[true_var])
                else:
                    state[dest].add(('unknown', 0))
                if false_var in state:
                    state[dest].update(state[false_var])
                else:
                    state[dest].add(('unknown', 0))
    return state

def get_used_defined_vars(instr):
    """
    Get used and defined variables from an instruction.
    """
    used = set()
    defined = set()
    dest = instr.get('dest')
    if dest:
        defined.add(dest)
    args = instr.get('args', [])
    if args:
        used.update(arg for arg in args if isinstance(arg, str))
    if 'op' in instr:
        op = instr['op']
        if op == 'store':
            # store x, p: x and p are used
            used.update(args[:2])
        elif op == 'load':
            # x = load p: p is used, x is defined
            pass  # Already handled
        elif op == 'call':
            # Function calls may use or define variables
            pass  # Already handled
    return used, defined

def liveness_analysis(blocks, cfg, labels):
    """
    Perform liveness analysis for variables.
    """
    block_map = dict(zip(labels, blocks))
    live_in = {label: set() for label in labels}
    live_out = {label: set() for label in labels}
    changed = True
    while changed:
        changed = False
        for label in reversed(labels):
            block = block_map[label]
            succs = cfg.get(label, [])
            out_set = set()
            for succ in succs:
                out_set.update(live_in[succ])
            old_in = live_in[label]
            live_out[label] = out_set
            in_set = analyze_liveness(block, live_out[label])
            live_in[label] = in_set
            if live_in[label] != old_in:
                changed = True
    return live_in, live_out

def analyze_liveness(block, live_out_set):
    """
    Analyze liveness within a single block.
    """
    live_vars = live_out_set.copy()
    for instr in reversed(block):
        used_vars, defined_vars = get_used_defined_vars(instr)
        live_vars -= defined_vars
        live_vars |= used_vars
    return live_vars

def memory_liveness_analysis(blocks, cfg, labels, alias_info):
    """
    Perform liveness analysis for memory locations.
    """
    block_map = dict(zip(labels, blocks))
    live_in = {label: set() for label in labels}
    live_out = {label: set() for label in labels}
    changed = True
    while changed:
        changed = False
        for label in reversed(labels):
            block = block_map[label]
            alias_maps = alias_info[label]
            succs = cfg.get(label, [])
            out_set = set()
            for succ in succs:
                out_set.update(live_in[succ])
            old_in = live_in[label]
            live_out[label] = out_set
            in_set = analyze_memory_uses(block, live_out[label], alias_maps)
            live_in[label] = in_set
            if live_in[label] != old_in:
                changed = True
    return live_in, live_out

def analyze_memory_uses(block, live_out_set, alias_maps):
    """
    Analyze memory uses within a single block.
    """
    live_set = live_out_set.copy()
    for idx in reversed(range(len(block))):
        instr = block[idx]
        alias_map = alias_maps[idx]
        if 'op' in instr:
            op = instr['op']
            args = instr.get('args', [])
            dest = instr.get('dest')
            if op == 'store':
                p = args[1]
                pts = alias_map.get(p, set())
                # Remove memory locations being overwritten
                live_set -= pts
                # Variables used are live
                live_set.update([p, args[0]])
            elif op == 'load':
                p = args[0]
                pts = alias_map.get(p, set())
                live_set.update(pts)
                live_set.update([p])
                live_set.discard(dest)
            elif op == 'free':
                p = args[0]
                pts = alias_map.get(p, set())
                live_set -= pts
                live_set.update([p])
            elif op == 'call':
                # Conservatively assume all memory locations could be used
                live_set.update({('unknown', 0)})
                # All arguments are used
                live_set.update(args)
                if dest:
                    live_set.discard(dest)
            elif op == 'ret':
                if args:
                    ret_var = args[0]
                    pts = alias_map.get(ret_var, set())
                    live_set.update(pts)
                    live_set.update([ret_var])
        # Handle variables
        used_vars, defined_vars = get_used_defined_vars(instr)
        live_set -= defined_vars
        live_set |= used_vars
    return live_set

def remove_dead_stores(func, alias_info, live_out):
    """
    Remove dead store instructions from the function.
    """
    blocks = list(form_blocks(func['instrs']))
    cfg, labels = construct_cfg(blocks)
    block_map = dict(zip(labels, blocks))
    for label in labels:
        block = block_map[label]
        alias_maps = alias_info[label]
        live_vars = live_out[label].copy()
        new_block = []
        for idx in reversed(range(len(block))):
            instr = block[idx]
            alias_map = alias_maps[idx]
            if 'op' in instr and instr['op'] == 'store':
                # Check if the memory location is live
                p = instr['args'][1]
                pts = alias_map.get(p, set())
                if pts.isdisjoint(live_vars):
                    # Dead store; remove it
                    logger.info(f"Removing dead store at instruction {instr}")
                    continue
                else:
                    new_block.append(instr)
                    used_vars, defined_vars = get_used_defined_vars(instr)
                    live_vars.update(used_vars)
                    live_vars -= defined_vars
                    live_vars.update(pts)
            else:
                used_vars, defined_vars = get_used_defined_vars(instr)
                live_vars -= defined_vars
                live_vars |= used_vars
                new_block.append(instr)
        block[:] = reversed(new_block)
    func['instrs'] = flatten([block_map[label] for label in labels])

def collect_alloc_sites(func):
    """
    Collect allocation sites within the function.
    """
    alloc_sites = {}
    counter = 0
    for instr in func['instrs']:
        if 'op' in instr and instr['op'] == 'alloc':
            alloc_sites[id(instr)] = f'alloc_{counter}'
            counter += 1
    return alloc_sites

def get_func_args(func):
    """
    Retrieve function arguments and their types.
    """
    args = {}
    for arg in func.get('args', []):
        arg_name = arg['name']
        arg_type = arg['type']
        args[arg_name] = arg_type
    return args

def optimize_function(func):
    """
    Optimize the given function by removing dead stores.
    """
    blocks = list(form_blocks(func['instrs']))
    cfg, labels = construct_cfg(blocks)
    alloc_sites = collect_alloc_sites(func)
    func_args = get_func_args(func)

    # Perform alias analysis
    in_alias, out_alias = alias_analysis(blocks, cfg, labels, func_args, alloc_sites)

    # Gather alias information at each instruction
    alias_info = {}
    block_map = dict(zip(labels, blocks))
    for label in labels:
        block = block_map[label]
        state = {var: locs.copy() for var, locs in in_alias.get(label, {}).items()}
        alias_maps = []
        for instr in block:
            alias_maps.append(state.copy())
            state = analyze_block([instr], state, alloc_sites)
        alias_info[label] = alias_maps

    # Perform variable liveness analysis
    live_in_vars, live_out_vars = liveness_analysis(blocks, cfg, labels)

    # Perform memory liveness analysis
    live_in_mem, live_out_mem = memory_liveness_analysis(blocks, cfg, labels, alias_info)

    # Combine live variables and live memory locations
    live_out = {}
    for label in labels:
        live_out[label] = live_out_vars[label] | live_out_mem[label]

    # Remove dead stores
    remove_dead_stores(func, alias_info, live_out)

def main():
    """
    Main function to optimize the program.
    """
    program = json.load(sys.stdin)
    for func in program['functions']:
        optimize_function(func)
    json.dump(program, sys.stdout, indent=2)

if __name__ == '__main__':
    main()
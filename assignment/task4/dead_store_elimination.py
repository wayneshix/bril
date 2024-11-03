import sys
import json
from collections import defaultdict, deque
from cfg import form_blocks
from cfg import flatten

def is_pointer_type(typ):
    """
    Helper function to check if a type is a pointer type.
    """
    if isinstance(typ, dict):
        return 'ptr' in typ
    elif isinstance(typ, str):
        return typ.startswith('ptr')
    else:
        return False

def construct_cfg(blocks):
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
    block_map = dict(zip(labels, blocks))
    in_state = {label: {} for label in labels}
    out_state = {label: {} for label in labels}

    # Initialize the analysis state
    init_state = {}
    for arg_name, arg_type in func_args.items():
        if is_pointer_type(arg_type):
            # Assign a base allocation site for each pointer argument with offset 0
            alloc_site = f'arg_{arg_name}'
            init_state[arg_name] = set([(alloc_site, 0)])

    worklist = deque(labels)
    while worklist:
        label = worklist.popleft()
        block = block_map[label]
        in_map = {}
        preds = [pred for pred in cfg if label in cfg[pred]]
        if preds:
            for pred in preds:
                pred_out = out_state[pred]
                for var in pred_out:
                    in_map.setdefault(var, set()).update(pred_out[var])
        else:
            in_map = {var: locs.copy() for var, locs in init_state.items()}

        # Update in_state
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
    state = {var: locs.copy() for var, locs in in_map.items()}
    for instr in block:
        if 'op' in instr:
            op = instr['op']
            dest = instr.get('dest')
            args = instr.get('args', [])
            if op == 'alloc':
                # x = alloc n: x points to this allocation at offset 0
                alloc_site = alloc_sites[id(instr)]
                state[dest] = set([(alloc_site, 0)])
            elif op == 'id':
                y = args[0]
                if y in state:
                    state[dest] = state[y].copy()
            elif op == 'ptradd':
                p = args[0]
                offset = args[1]
                if p in state:
                    base_points_to = state[p]
                    new_points_to = set()
                    try:
                        offset_value = int(offset)
                    except ValueError:
                        # Offset is not a constant, conservatively use unknown
                        new_points_to.add(('unknown', 0))
                    else:
                        for alloc_site, base_offset in base_points_to:
                            new_offset = base_offset + offset_value
                            new_points_to.add((alloc_site, new_offset))
                    state[dest] = new_points_to
                else:
                    state[dest] = set([('unknown', 0)])
            elif op == 'load':
                # x = load p: x may point to unknown memory
                state[dest] = set([('unknown', 0)])
            elif op == 'call':
                # Function calls can change pointers conservatively
                dest = instr.get('dest')
                if dest:
                    dest_type = instr.get('type')
                    if is_pointer_type(dest_type):
                        state[dest] = set([('unknown', 0)])
    return state

def get_used_defined_vars(instr):
    used = set()
    defined = set()
    if 'dest' in instr:
        defined.add(instr['dest'])
    if 'args' in instr:
        used.update(instr['args'])
    if 'op' in instr:
        op = instr['op']
        if op == 'store':
            # store p x: p and x are used
            used.update(instr['args'])
            defined.discard(instr.get('dest', None))
        elif op == 'load':
            # x = load p: p is used, x is defined
            pass  # already handled
        elif op == 'call':
            # Function calls may use or define variables
            # For simplicity, assume all args are used and dest is defined
            pass  # already handled
    return used, defined

def liveness_analysis(blocks, cfg, labels):
    block_map = dict(zip(labels, blocks))
    live_in = {label: set() for label in labels}
    live_out = {label: set() for label in labels}
    changed = True
    while changed:
        changed = False
        for label in reversed(labels):
            block = block_map[label]
            out_set = set()
            succs = cfg.get(label, [])
            for succ in succs:
                out_set.update(live_in[succ])
            old_in = live_in[label].copy()
            live_out[label] = out_set.copy()
            in_set = analyze_liveness(block, live_out[label])
            live_in[label] = in_set
            if live_in[label] != old_in:
                changed = True
    return live_in, live_out

def analyze_liveness(block, live_out_set):
    live_vars = live_out_set.copy()
    for instr in reversed(block):
        used_vars, defined_vars = get_used_defined_vars(instr)
        live_vars -= defined_vars
        live_vars |= used_vars
    return live_vars

def memory_liveness_analysis(blocks, cfg, labels, alias_info):
    block_map = dict(zip(labels, blocks))
    live_in = {label: set() for label in labels}
    live_out = {label: set() for label in labels}
    changed = True
    while changed:
        changed = False
        for label in reversed(labels):
            block = block_map[label]
            alias_maps = alias_info[label]
            out_set = set()
            succs = cfg.get(label, [])
            for succ in succs:
                out_set.update(live_in[succ])
            old_in = live_in[label].copy()
            live_out[label] = out_set.copy()
            in_set = analyze_memory_uses(block, live_out[label], alias_maps)
            live_in[label] = in_set
            if live_in[label] != old_in:
                changed = True
    return live_in, live_out

def analyze_memory_uses(block, live_out_set, alias_maps):
    live_set = live_out_set.copy()
    for idx in reversed(range(len(block))):
        instr = block[idx]
        alias_map = alias_maps[idx]
        if 'op' in instr:
            op = instr['op']
            args = instr.get('args', [])
            dest = instr.get('dest')
            if op == 'store':
                p = args[0]
                pts = alias_map.get(p, set())
                # Remove the memory locations from live set
                live_set -= pts
                # Variables used are live
                live_set.add(p)
                live_set.add(args[1])  # The value being stored
            elif op == 'load':
                p = args[0]
                pts = alias_map.get(p, set())
                live_set.update(pts)
                # Variables used are live
                live_set.add(p)
                # dest is defined
                live_set.discard(dest)
            elif op == 'free':
                p = args[0]
                pts = alias_map.get(p, set())
                live_set -= pts
                live_set.add(p)
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
                    live_set.add(ret_var)
        # Handle variables
        used_vars, defined_vars = get_used_defined_vars(instr)
        live_set -= defined_vars
        live_set |= used_vars
    return live_set

def remove_dead_stores(func, alias_info, live_out):
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
            used_vars, defined_vars = get_used_defined_vars(instr)
            if 'op' in instr and instr['op'] == 'store':
                # For 'store', unless we are certain it's dead, we keep it
                p = instr['args'][0]
                x = instr['args'][1]
                pts = alias_map.get(p, set())
                # Retain the 'store' unless we can guarantee it's dead
                new_block.append(instr)
                live_vars.update(used_vars)
                live_vars -= defined_vars
                live_vars.update(pts)
            else:
                # Update live_vars
                live_vars -= defined_vars
                live_vars |= used_vars
                new_block.append(instr)
        block[:] = reversed(new_block)
    func['instrs'] = flatten([block_map[label] for label in labels])

def collect_alloc_sites(func):
    alloc_sites = {}
    counter = 0
    for instr in func['instrs']:
        if 'op' in instr and instr['op'] == 'alloc':
            alloc_sites[id(instr)] = f'alloc_{counter}'
            counter += 1
    return alloc_sites

def get_func_args(func):
    args = {}
    for arg in func.get('args', []):
        arg_name = arg['name']
        arg_type = arg['type']
        args[arg_name] = arg_type
    return args

def optimize_function(func):
    blocks = list(form_blocks(func['instrs']))
    cfg, labels = construct_cfg(blocks)
    alloc_sites = collect_alloc_sites(func)
    func_args = get_func_args(func)
    # Perform alias analysis
    in_alias, out_alias = alias_analysis(blocks, cfg, labels, func_args, alloc_sites)
    # Get alias info at each instruction
    alias_info = {}
    block_map = dict(zip(labels, blocks))
    for label in labels:
        block = block_map[label]
        state = {var: locs.copy() for var, locs in in_alias.get(label, {}).items()}
        alias_maps = []
        for instr in block:
            alias_maps.append(state.copy())
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
                elif op == 'ptradd':
                    p = args[0]
                    offset = args[1]
                    if p in state:
                        base_points_to = state[p]
                        new_points_to = set()
                        try:
                            offset_value = int(offset)
                        except ValueError:
                            # Offset is not a constant, conservatively use unknown
                            new_points_to.add(('unknown', 0))
                        else:
                            for alloc_site, base_offset in base_points_to:
                                new_offset = base_offset + offset_value
                                new_points_to.add((alloc_site, new_offset))
                        state[dest] = new_points_to
                    else:
                        state[dest] = set([('unknown', 0)])
                elif op == 'load':
                    state[dest] = set([('unknown', 0)])
                elif op == 'call':
                    dest = instr.get('dest')
                    if dest:
                        dest_type = instr.get('type')
                        if is_pointer_type(dest_type):
                            state[dest] = set([('unknown', 0)])
        alias_info[label] = alias_maps  # Store the list of alias maps
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
    program = json.load(sys.stdin)
    for func in program['functions']:
        optimize_function(func)
    json.dump(program, sys.stdout, indent=2)

if __name__ == '__main__':
    main()
import sys
import json
from collections import defaultdict

def form_blocks(instrs):
    blocks = []
    current_block = []
    for instr in instrs:
        if 'label' in instr:
            if current_block:
                blocks.append(current_block)
            current_block = [instr]
        else:
            current_block.append(instr)
            if 'op' in instr and instr['op'] in ['jmp', 'br', 'ret']:
                blocks.append(current_block)
                current_block = []
    if current_block:
        blocks.append(current_block)
    return blocks

def build_cfg(blocks):
    block_map = {}
    labels = {}
    for i, block in enumerate(blocks):
        if 'label' in block[0]:
            label = block[0]['label']
        else:
            label = f'block_{i}'
            block.insert(0, {'label': label})
        block_map[label] = block
        labels[label] = i
    cfg = {label: [] for label in block_map}
    for i, block in enumerate(blocks):
        label = block[0]['label']
        last_instr = block[-1]
        if 'op' in last_instr:
            if last_instr['op'] == 'jmp':
                cfg[label].append(last_instr['labels'][0])
            elif last_instr['op'] == 'br':
                cfg[label].extend(last_instr['labels'])
            elif last_instr['op'] == 'ret':
                pass  # No successors
            else:
                # Fallthrough
                if i + 1 < len(blocks):
                    next_label = blocks[i+1][0]['label']
                    cfg[label].append(next_label)
        else:
            # Fallthrough
            if i + 1 < len(blocks):
                next_label = blocks[i+1][0]['label']
                cfg[label].append(next_label)
    return block_map, cfg

def get_predecessors(cfg, node):
    preds = []
    for n in cfg:
        if node in cfg[n]:
            preds.append(n)
    return preds

def compute_dominators(cfg, entry):
    dominators = {node: set(cfg.keys()) for node in cfg}
    dominators[entry] = {entry}
    changed = True
    while changed:
        changed = False
        for node in cfg:
            if node == entry:
                continue
            preds = get_predecessors(cfg, node)
            if not preds:
                continue
            new_doms = set(cfg.keys())
            for pred in preds:
                new_doms &= dominators[pred]
            new_doms.add(node)
            if dominators[node] != new_doms:
                dominators[node] = new_doms
                changed = True
    return dominators

def find_back_edges(cfg, dominators):
    back_edges = []
    for src in cfg:
        for dest in cfg[src]:
            if dest in dominators[src]:
                back_edges.append((src, dest))
    return back_edges

def find_natural_loops(cfg, back_edges):
    loops = []
    for src, dest in back_edges:
        loop_nodes = set()
        stack = [src]
        while stack:
            n = stack.pop()
            if n not in loop_nodes:
                loop_nodes.add(n)
                preds = get_predecessors(cfg, n)
                stack.extend(preds)
        loops.append((dest, loop_nodes))
    return loops

def get_defs_outside_loop(block_map, loop_blocks):
    defs_outside = set()
    for label in block_map:
        if label not in loop_blocks:
            block = block_map[label]
            for instr in block:
                if 'dest' in instr:
                    defs_outside.add(instr['dest'])
    return defs_outside

def find_pure_functions(prog):
    """
    Identify pure functions (functions without side effects) in the program.
    """
    pure_functions = set()
    for func in prog['functions']:
        has_side_effect = False
        for instr in func.get('instrs', []):
            if instr.get('op') in ['print', 'store', 'free', 'speculate', 'guard']:
                has_side_effect = True
                break
            if instr.get('op') == 'call':
                # For simplicity, assume functions calling other functions may have side effects
                has_side_effect = True
                break
        if not has_side_effect:
            pure_functions.add(func['name'])
    return pure_functions

def has_side_effects(instr, pure_functions):
    if instr.get('op') in ['print', 'store', 'free', 'speculate', 'guard']:
        return True
    if instr.get('op') == 'call':
        # Allow calls to pure functions
        func_name = instr['funcs'][0]
        return func_name not in pure_functions
    return False

def find_loop_invariants(block_map, loop_blocks, defs_outside_loop, var_modified_in_loop, pure_functions):
    invariant_instrs = []
    invariant_vars = set()
    changed = True

    while changed:
        changed = False
        for block_label in loop_blocks:
            block = block_map[block_label]
            for instr in block[:]:
                if 'dest' not in instr:
                    continue
                dest_var = instr['dest']
                if dest_var in invariant_vars:
                    continue
                if has_side_effects(instr, pure_functions):
                    continue
                args = instr.get('args', [])
                # Skip if any arg is modified in the loop and not invariant
                if any(arg in var_modified_in_loop and arg not in invariant_vars for arg in args):
                    continue
                # Check if all args are defined outside the loop or are invariant
                if all(arg in defs_outside_loop or arg in invariant_vars for arg in args):
                    # Move instruction
                    invariant_instrs.append((block_label, instr))
                    invariant_vars.add(dest_var)
                    block.remove(instr)
                    changed = True
    return invariant_instrs

def insert_preheader(block_map, cfg, loop_blocks, header_label):
    preheader_label = f'{header_label}_preheader'
    preheader_block = [{'label': preheader_label}]
    preds = get_predecessors(cfg, header_label)
    outside_preds = [p for p in preds if p not in loop_blocks]
    # Update cfg
    cfg[preheader_label] = [header_label]
    for pred in outside_preds:
        cfg[pred] = [preheader_label if s == header_label else s for s in cfg[pred]]
    # Update block map
    block_map[preheader_label] = preheader_block
    return preheader_label

def move_invariants_to_preheader(block_map, invariant_instrs, preheader_label):
    preheader_block = block_map[preheader_label]
    for _, instr in invariant_instrs:
        preheader_block.append(instr)
def licm_function(func, pure_functions):
    instrs = func['instrs']
    blocks = form_blocks(instrs)
    block_map, cfg = build_cfg(blocks)
    if not blocks:
        return  # Empty function
    entry_label = blocks[0][0]['label']
    dominators = compute_dominators(cfg, entry_label)
    back_edges = find_back_edges(cfg, dominators)
    natural_loops = find_natural_loops(cfg, back_edges)
    for header_label, loop_blocks in natural_loops:
        defs_outside_loop = get_defs_outside_loop(block_map, loop_blocks)
        var_modified_in_loop = set()
        # Collect variables modified within the loop
        for block_label in loop_blocks:
            block = block_map[block_label]
            for instr in block:
                if 'dest' in instr:
                    var_modified_in_loop.add(instr['dest'])
        invariant_instrs = find_loop_invariants(block_map, loop_blocks, defs_outside_loop, var_modified_in_loop, pure_functions)
        if invariant_instrs:
            preheader_label = insert_preheader(block_map, cfg, loop_blocks, header_label)
            move_invariants_to_preheader(block_map, invariant_instrs, preheader_label)
    # Reconstruct the function instrs
    new_instrs = []
    visited = set()
    def dfs(label):
        if label in visited:
            return
        visited.add(label)
        block = block_map[label]
        new_instrs.extend(block)
        for succ in cfg.get(label, []):
            dfs(succ)
    dfs(entry_label)
    func['instrs'] = new_instrs

def licm_program(prog):
    # Identify pure functions in the program
    pure_functions = find_pure_functions(prog)
    for func in prog['functions']:
        licm_function(func, pure_functions)
    return prog

def main():
    prog = json.load(sys.stdin)
    prog = licm_program(prog)
    print(json.dumps(prog, indent=2))

if __name__ == "__main__":
    main()
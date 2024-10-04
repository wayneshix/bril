import sys
import json
from collections import defaultdict, deque
from form_blocks import form_blocks
from util import flatten

def is_constant(instr):
    """Check if an instruction defines a constant value."""
    return instr.get('op') == 'const'

def get_const_value(instr):
    """Retrieve the constant value from a 'const' instruction."""
    return instr['value']

def build_cfg(blocks):
    """Build the Control Flow Graph (CFG) from the list of blocks."""
    labels = [block[0]['label'] if 'label' in block[0] else f'<bb{idx}>' for idx, block in enumerate(blocks)]
    cfg = {label: [] for label in labels}
    for idx, block in enumerate(blocks):
        label = labels[idx]
        last_instr = block[-1] if block else None
        if last_instr and 'op' in last_instr:
            if last_instr['op'] == 'br':
                cfg[label].extend(last_instr['labels'])
            elif last_instr['op'] == 'jmp':
                cfg[label].append(last_instr['labels'][0])
            else:
                if idx + 1 < len(blocks):
                    cfg[label].append(labels[idx + 1])
        else:
            if idx + 1 < len(blocks):
                cfg[label].append(labels[idx + 1])
    return cfg, labels

def reverse_cfg(cfg):
    """Build the reverse CFG (mapping from a node to its predecessors)."""
    rev_cfg = defaultdict(set)
    for node, succs in cfg.items():
        for succ in succs:
            rev_cfg[succ].add(node)
    return rev_cfg

def intersect(s1, s2):
    """Intersect two dictionaries representing variable constants."""
    result = {}
    for var in s1:
        if var in s2 and s1[var] == s2[var]:
            result[var] = s1[var]
    return result

def intersect_all(dicts):
    """Intersect a list of dictionaries representing variable constants."""
    if not dicts:
        return {}
    result = dicts[0].copy()
    for d in dicts[1:]:
        result = intersect(result, d)
    return result

def worklist_algorithm(blocks, cfg, labels):
    """Perform constant propagation using a worklist algorithm."""
    in_consts = {}
    out_consts = {}

    # Initialize in_consts and out_consts
    for label in labels:
        in_consts[label] = {}
        out_consts[label] = {}

    entry_label = labels[0]
    out_consts[entry_label] = {}

    worklist = deque(labels)

    while worklist:
        label = worklist.popleft()
        block = next(block for block in blocks if ('label' in block[0] and block[0]['label'] == label) or ('label' not in block[0] and label.startswith('<bb')))
        preds = [pred for pred in cfg if label in cfg[pred]]
        if preds:
            in_consts[label] = intersect_all([out_consts[pred] for pred in preds])
        else:
            in_consts[label] = {}

        old_out_consts = out_consts[label].copy()
        out_consts[label] = transfer_function(block, in_consts[label])

        if old_out_consts != out_consts[label]:
            for succ in cfg[label]:
                if succ not in worklist:
                    worklist.append(succ)

    return in_consts, out_consts

def transfer_function(block, in_consts):
    """Compute the out_consts for a block given in_consts."""
    out_consts = in_consts.copy()
    for instr in block:

        if 'op' not in instr:
            continue 

        if 'dest' in instr:
            dest = instr['dest']
            if instr['op'] == 'const':

                out_consts[dest] = instr['value']
                print(f"Propagating constant {instr['value']} to {dest}", file=sys.stderr)
            elif instr['op'] in ['add', 'mul', 'sub', 'div', 'eq', 'lt', 'gt', 'le', 'ge', 'not', 'and', 'or']:

                args = instr.get('args', [])
                const_args = [out_consts.get(arg) for arg in args]
                if all(const_arg is not None for const_arg in const_args):
                    try:
                        result = evaluate(instr['op'], const_args)
                        out_consts[dest] = result
                        print(f"Folding constant expression {instr['op']} -> {result}", file=sys.stderr)
                    except ZeroDivisionError:
                        if dest in out_consts:
                            del out_consts[dest]
                            print(f"Division by zero detected, removing {dest}", file=sys.stderr)
                else:
                    if dest in out_consts:
                        del out_consts[dest]
            else:
  
                if dest in out_consts:
                    del out_consts[dest]
        else:

            pass
    return out_consts

def evaluate(op, args):
    """Evaluate an operation with constant arguments."""
    if op == 'add':
        return args[0] + args[1]
    elif op == 'sub':
        return args[0] - args[1]
    elif op == 'mul':
        return args[0] * args[1]
    elif op == 'div':
        return args[0] // args[1]
    elif op == 'eq':
        return int(args[0] == args[1])
    elif op == 'lt':
        return int(args[0] < args[1])
    elif op == 'gt':
        return int(args[0] > args[1])
    elif op == 'le':
        return int(args[0] <= args[1])
    elif op == 'ge':
        return int(args[0] >= args[1])
    elif op == 'not':
        return int(not args[0])
    elif op == 'and':
        return int(args[0] and args[1])
    elif op == 'or':
        return int(args[0] or args[1])
    else:
        raise ValueError(f"Unsupported operation: {op}")

def apply_constant_propagation(func):
    """Apply global constant propagation and folding to a function."""
    blocks = list(form_blocks(func['instrs']))
    cfg, labels = build_cfg(blocks)
    in_consts, out_consts = worklist_algorithm(blocks, cfg, labels)


    label2block = {}
    for block in blocks:
        if 'label' in block[0]:
            label = block[0]['label']
        else:
            label = f'<bb{blocks.index(block)}>'
        label2block[label] = block

    for label in labels:
        block = label2block[label]
        constants = in_consts[label]
        new_block = []
        for instr in block:
            if 'op' not in instr:
                new_block.append(instr) 
                continue

            if instr['op'] == 'const':
                new_block.append(instr)
            elif instr['op'] == 'br':
                cond = instr['args'][0]
                if cond in constants:
                    cond_value = constants[cond]
                    if cond_value == 1:
                        instr = {
                            'op': 'jmp',
                            'labels': [instr['labels'][0]]
                        }
                    elif cond_value == 0:
                        instr = {
                            'op': 'jmp',
                            'labels': [instr['labels'][1]]
                        }
                    else:
                        pass
                    print(f"Folding branch based on constant {cond_value}", file=sys.stderr)
                new_block.append(instr)
            elif instr['op'] in ['print', 'jmp', 'ret']:
                new_block.append(instr)
            elif instr['op'] in ['add', 'mul', 'sub', 'div', 'eq', 'lt', 'gt', 'le', 'ge', 'not', 'and', 'or']:
                args = instr.get('args', [])
                const_args = [constants.get(arg) for arg in args]
                if all(const_arg is not None for const_arg in const_args):
                    try:
                        result = evaluate(instr['op'], const_args)
                        instr = {
                            'op': 'const',
                            'dest': instr['dest'],
                            'type': instr['type'],
                            'value': result
                        }
                        print(f"Replacing computation with constant {result} in {instr['dest']}", file=sys.stderr)
                    except ZeroDivisionError:
                        pass
                new_block.append(instr)
            else:
                new_block.append(instr)
        label2block[label] = new_block

    func['instrs'] = flatten([label2block[label] for label in labels])

def main():
    prog = json.load(sys.stdin)

    for func in prog['functions']:
        apply_constant_propagation(func)

    json.dump(prog, sys.stdout, indent=2)

if __name__ == "__main__":
    main()
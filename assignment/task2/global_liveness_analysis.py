import sys
import json
from collections import defaultdict, deque
from form_blocks import form_blocks
from util import flatten

def is_critical(instr):
    """Check if an instruction is critical and cannot be removed."""
    if 'op' not in instr:
        return False
    return instr['op'] in ('print', 'br', 'jmp', 'ret', 'call', 'store', 'free')

def build_cfg(blocks):
    """Build the Control Flow Graph (CFG) from the list of blocks."""
    labels = []
    label2block = {}
    for idx, block in enumerate(blocks):
        if 'label' in block[0]:
            label = block[0]['label']
        else:
            label = f'<bb{idx}>'
        labels.append(label)
        label2block[label] = block

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

def compute_liveness(blocks, cfg, labels):
    """Compute live-in and live-out sets for each block."""
    label2block = {label: block for label, block in zip(labels, blocks)}

    live_in = {label: set() for label in labels}
    live_out = {label: set() for label in labels}
    use = {}
    defs = {}
    for label in labels:
        block = label2block[label]
        block_defs = set()
        block_use = set()
        for instr in block:
            if 'op' in instr:
                args = instr.get('args', [])
                dest = instr.get('dest')
                for arg in args:
                    if arg not in block_defs:
                        block_use.add(arg)
                if dest:
                    block_defs.add(dest)
        use[label] = block_use
        defs[label] = block_defs


    changed = True
    while changed:
        changed = False
        for label in reversed(labels):
            old_live_in = live_in[label].copy()
            old_live_out = live_out[label].copy()


            succs = cfg[label]
            live_out[label] = set()
            for succ in succs:
                live_out[label].update(live_in[succ])


            live_in[label] = use[label].union(live_out[label] - defs[label])

            if live_in[label] != old_live_in or live_out[label] != old_live_out:
                changed = True

    return live_in, live_out

def eliminate_dead_code(func):
    """Perform dead code elimination on a function using liveness analysis."""
    blocks = list(form_blocks(func['instrs']))
    cfg, labels = build_cfg(blocks)
    live_in, live_out = compute_liveness(blocks, cfg, labels)

    label2block = {label: block for label, block in zip(labels, blocks)}
    for label in labels:
        block = label2block[label]
        live = live_out[label].copy()
        new_block = []
        for instr in reversed(block):
            if 'op' not in instr:
                new_block.append(instr)
                continue
            dest = instr.get('dest')
            args = instr.get('args', [])
            if is_critical(instr) or (dest and dest in live):
                new_block.append(instr)
                if dest:
                    live.discard(dest)
                live.update(args)
            else:

                pass
        block[:] = reversed(new_block)

    func['instrs'] = flatten([label2block[label] for label in labels])

def main():
    prog = json.load(sys.stdin)

    for func in prog['functions']:
        eliminate_dead_code(func)

    json.dump(prog, sys.stdout, indent=2)

if __name__ == "__main__":
    main()
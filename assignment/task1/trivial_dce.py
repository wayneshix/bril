import sys
import json
from form_blocks import form_blocks
from util import flatten

def is_critical(instr):
    if 'op' not in instr:
        return False
    return instr['op'] in ('print', 'br', 'jmp', 'ret', 'call')

def compute_reachable_blocks(cfg, entry_label):
    visited = set()
    stack = [entry_label]
    while stack:
        label = stack.pop()
        if label not in visited:
            visited.add(label)
            stack.extend(cfg.get(label, []))
    return visited

def trivial_global_dce(func):
    """Perform global dead code elimination across all blocks of a function."""
    blocks = list(form_blocks(func['instrs']))
    label2block = {}
    block_labels = []
    unnamed_label_counter = 0
    for block in blocks:
        if len(block) > 0 and 'label' in block[0]:
            label = block[0]['label']
        else:
            label = f'<unnamed_{unnamed_label_counter}>'
            unnamed_label_counter += 1
        label2block[label] = block
        block_labels.append(label)
    
    cfg = {}
    for i, block in enumerate(blocks):
        label = block_labels[i]
        cfg[label] = []
        if len(block) == 0:
            continue
        last_instr = block[-1]
        if last_instr.get('op') == 'jmp':
            cfg[label].append(last_instr['labels'][0])
        elif last_instr.get('op') == 'br':
            cfg[label].append(last_instr['labels'][0])
            cfg[label].append(last_instr['labels'][1])
        else:

            if i+1 < len(blocks):
                cfg[label].append(block_labels[i+1])
    
    entry_label = block_labels[0]
    reachable_blocks = compute_reachable_blocks(cfg, entry_label)
    
    block_labels = [label for label in block_labels if label in reachable_blocks]
    blocks = [label2block[label] for label in block_labels]
    
    liveIn = {label: set() for label in block_labels}
    liveOut = {label: set() for label in block_labels}
    
    Defs = {}
    Uses = {}
    for label, block in zip(block_labels, blocks):
        defs = set()
        uses = set()
        for instr in block:
            instr_args = instr.get('args', [])
            instr_dest = instr.get('dest')
            if 'op' not in instr:
                continue
            uses.update(arg for arg in instr_args if arg not in defs)
            if instr_dest:
                defs.add(instr_dest)
        Defs[label] = defs
        Uses[label] = uses
    
    changed = True
    while changed:
        changed = False
        for label in reversed(block_labels):
            old_liveIn = liveIn[label].copy()
            liveOut[label] = set()
            for succ in cfg.get(label, []):
                if succ in liveIn:
                    liveOut[label].update(liveIn[succ])
            liveIn[label] = (liveOut[label] - Defs[label]) | Uses[label]
            if liveIn[label] != old_liveIn:
                changed = True

    overall_changed = False
    for label, block in zip(block_labels, blocks):
        live = liveOut[label].copy()
        new_block = []
        for instr in reversed(block):
            instr_args = instr.get('args', [])
            instr_dest = instr.get('dest')
            if 'op' not in instr:
                # It's a label, keep it
                new_block.append(instr)
                continue
            if is_critical(instr) or (instr_dest and instr_dest in live):
                new_block.append(instr)
                if instr_dest:
                    live.discard(instr_dest)
                live.update(instr_args)
            else:
                if instr_dest or instr.get('op') != 'nop':
                    overall_changed = True
        block[:] = reversed(new_block)
    func['instrs'] = flatten(blocks)
    return overall_changed

def apply_global_dce(bril_program):
    for func in bril_program['functions']:
        while trivial_global_dce(func):
            pass

def main():
    bril_program = json.load(sys.stdin)
    apply_global_dce(bril_program)
    json.dump(bril_program, sys.stdout, indent=2, sort_keys=True)

if __name__ == '__main__':
    main()

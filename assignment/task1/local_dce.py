#!/usr/bin/env python3

import sys
import json
from form_blocks import form_blocks
from util import flatten

def is_critical(instr):
    if 'op' not in instr:
        return False
    return instr['op'] in ('print', 'ret', 'call')

def local_dce_block(block):
    """Perform local dead code elimination on a single basic block.

    Args:
        block: List of instructions in the basic block.

    Returns:
        True if any instructions were removed; False otherwise.
    """
    live = set()
    new_block = []
    changed = False

    for instr in reversed(block):
        instr_args = instr.get('args', [])
        instr_dest = instr.get('dest')

        if 'op' not in instr:
            new_block.append(instr)
            continue

        if is_critical(instr) or (instr_dest and instr_dest in live):
            new_block.append(instr)
            live.difference_update([instr_dest])
            live.update(instr_args)   
        else:
            changed = True

    block[:] = reversed(new_block)
    return changed

def local_dce_func(func):
    """Perform local dead code elimination on a function.

    Args:
        func: A function dictionary from a Bril program.

    Returns:
        True if any instructions were removed; False otherwise.
    """
    blocks = list(form_blocks(func['instrs']))
    overall_changed = False

    for block in blocks:
        changed = local_dce_block(block)
        overall_changed |= changed

    func['instrs'] = flatten(blocks)
    return overall_changed

def apply_local_dce(bril_program):
    for func in bril_program['functions']:
        local_dce_func(func)

def main():
    bril_program = json.load(sys.stdin)
    apply_local_dce(bril_program)
    json.dump(bril_program, sys.stdout, indent=2, sort_keys=True)

if __name__ == '__main__':
    main()

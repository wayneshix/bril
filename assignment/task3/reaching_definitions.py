import sys
import json
import click
from collections import OrderedDict

from cfg import form_cfg, form_blocks, form_block_dict
from bril_core_constants import *
from worklist_solver import Worklist


def kills(block):
    assert type(block) == list
    kills = set()
    for i, instr in block:
        if DEST in instr:
            dst = instr[DEST]
            kills.add((i, dst))
    return kills


def defs(block):
    assert type(block) == list
    variables = dict()
    for (idx, instr) in block:
        if DEST in instr:
            dst = instr[DEST]
            # get most recent variable assignment to dst in basic block
            variables[dst] = idx

    defs = set()
    for dst, idx in variables.items():
        defs.add((idx, dst))
    return defs


def diff(in_block, kills):
    assert type(in_block) == set
    assert type(kills) == set
    final = set()
    for (i1, var1) in in_block:
        killed = False
        for (_, var2) in kills:
            if var1 == var2:
                killed = True
                break
        if not killed:
            final.add((i1, var1))
    return final


def transfer(in_block, block):
    assert type(in_block) == set
    assert type(block) == list
    return defs(block).union(diff(in_block, kills(block)))


def merge(blocks):
    merged = set()
    for b in blocks:
        merged = merged.union(b)
    return merged


def number_instrs(blocks):
    """
    Adds unique instruction labels to every instruction
    """
    i = 1
    new_blocks = {}
    for key, block in blocks.items():
        new_block = []
        for instr in block:
            new_block.append((i, instr))
            i += 1
        new_blocks[key] = new_block
    return new_blocks


def reaching_defs_func(function):
    cfg = form_cfg(function)
    assert len(cfg) != 0
    entry = list(cfg.items())[0][0]
    blocks = number_instrs(form_block_dict(form_blocks(function["instrs"])))
    init = set()
    if ARGS in function:
        args = function[ARGS]
        for i, a in enumerate(args, 1):
            init.add((-i, a[NAME]))
    worklist = Worklist(entry, cfg, blocks, init, merge, transfer)
    return worklist.solve()


def reaching_defs(program):
    for func in program["functions"]:
        (in_dict, out_dict) = reaching_defs_func(func)

        final_in_dict = OrderedDict()
        for (key, inner_set) in in_dict.items():
            inner_lst = list(
                sorted([pair for pair in inner_set], key=lambda pair: pair[0]))
            final_in_dict[key] = inner_lst
        final_out_dict = OrderedDict()
        for (key, inner_set) in out_dict.items():
            inner_lst = list(
                sorted([pair for pair in inner_set], key=lambda pair: pair[0]))
            final_out_dict[key] = inner_lst

        print(f"Function: {func[NAME]}")
        print(f"In:")
        for (k, v) in final_in_dict.items():
            if v == []:
                print(f"\t{k}: No Reaching Definitions.")
            else:
                for (idx, var) in v:
                    print(f"\t{k}: {var} on line {idx}.")
        print(f"Out:")
        for (k, v) in final_out_dict.items():
            if v == []:
                print(f"\t{k}: No Reaching Definitions.")
            else:
                for (idx, var) in v:
                    print(f"\t{k}: {var} on line {idx}.")
    return


@click.command()
@click.option('--pretty-print', default=False, help='Pretty Print Original Program.')
def main(pretty_print):
    prog = json.load(sys.stdin)
    if pretty_print:
        print(json.dumps(prog, indent=4, sort_keys=True))
    reaching_defs(prog)


if __name__ == "__main__":
    main()
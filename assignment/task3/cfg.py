import json
import sys
from collections import OrderedDict
from copy import deepcopy

from bril_core_constants import *
from bril_core_utilities import is_br, is_jmp, is_label

TERMINATORS = ["jmp", "br", "ret"]

PREDS = "preds"
SUCCS = "succs"
INSTRS = "instrs"


def form_cfg_succs_preds(body):
    """
    Takes a Function Body and turns it into a CFG
    representation with Successors and Predecessors with Multiple Basic Blocks
    """
    assert type(body) == list
    blocks = form_blocks(body)
    name2block = form_block_dict(blocks)
    succs_cfg = get_cfg(name2block)
    preds_cfg = OrderedDict()
    for bb_name in succs_cfg:
        preds = []
        for bb_name1, succs in succs_cfg.items():
            if bb_name in succs:
                preds.append(bb_name1)
        preds_cfg[bb_name] = preds

    out = OrderedDict()
    for bb_name in succs_cfg:
        out[bb_name] = {PREDS: preds_cfg[bb_name], SUCCS: succs_cfg[bb_name]}
    return out


def form_blocks(body):
    cur_block = []
    for instr in body:
        if "op" in instr:
            cur_block.append(instr)
            if instr["op"] in TERMINATORS:
                yield cur_block
                cur_block = []
        else:
            if cur_block:
                yield cur_block
            cur_block = [instr]
    if cur_block:
        yield cur_block


def join_blocks(blocks):
    """
    Joins a list of basic blocks into 1 function body
    Inverts form_blocks
    """
    new_instrs = []
    for bb in blocks:
        for instr in bb:
            new_instrs.append(instr)
    return new_instrs


def join_blocks_w_labels(block_dict):
    """
    Joins a dictionary of basic blocks into 1 function body
    Inverts form_blocks, But adds label if label instr was not there previously
    """
    new_instrs = []
    for label, bb in block_dict.items():
        if len(bb) != 0 and 'label' not in bb[0]:
            new_instrs.append({'label': label})
        for instr in bb:
            new_instrs.append(instr)
    return new_instrs


def block_map(blocks):
    """
    Converts a list of basic blocks into a map of label to the instructions in block
    """
    out = OrderedDict()

    for i, block in enumerate(blocks):
        if 'label' in block[0]:
            name = block[0]['label']
            block = block[1:]
        else:
            name = f'b{i}'
        out[name] = block

    return out


def form_block_dict(blocks):
    """
    Similar to Block Map: But retain labels in instructions
    Internally Preserves labels, unlike Block Map, which tries to remove labels
    and use them solely as dictionary keys.
    """
    out = OrderedDict()

    for i, block in enumerate(blocks):
        if 'label' in block[0]:
            name = block[0]['label']
        else:
            name = f'b{i}'
        out[name] = block

    return out


def get_cfg(name2block):
    """
    Converts Name2Block into a Successor Labeled CFG
    """
    out = OrderedDict()
    for i, (name, block) in enumerate(name2block.items()):
        if block != []:
            last = block[-1]
            if 'op' in last and last['op'] in ['jmp', 'br']:
                succ = last['labels']
            elif 'op' in last and last['op'] == 'ret':
                succ = []
            else:
                if i == len(name2block) - 1:
                    succ = []
                else:
                    succ = [list(name2block.keys())[i + 1]]
            out[name] = succ
        else:
            if i == len(name2block) - 1:
                succ = []
            else:
                succ = [list(name2block.keys())[i + 1]]
            out[name] = succ
    return out


def get_cfg_w_blocks(name2block):
    """
    Converts Name2Block into a Successor, Predecessor Labeled CFG,
    WITH BLOCKS of Instructions
    """
    succs_cfg = OrderedDict()
    for i, (name, block) in enumerate(name2block.items()):
        if block != []:
            last = block[-1]
            if 'op' in last and last['op'] in ['jmp', 'br']:
                succ = last['labels']
            elif 'op' in last and last['op'] == 'ret':
                succ = []
            else:
                if i == len(name2block) - 1:
                    succ = []
                else:
                    succ = [list(name2block.keys())[i + 1]]
            result = {INSTRS: block, SUCCS: succ, PREDS: []}
            succs_cfg[name] = result
        else:
            if i == len(name2block) - 1:
                succ = []
            else:
                succ = [list(name2block.keys())[i + 1]]
            result = {INSTRS: block, SUCCS: succ, PREDS: []}
            succs_cfg[name] = result

    preds_cfg = OrderedDict()
    for bb_name in succs_cfg:
        preds = []
        for bb_name_pred, triple_dict in succs_cfg.items():
            if bb_name in triple_dict[SUCCS]:
                preds.append(bb_name_pred)
        preds_cfg[bb_name] = preds

    out = OrderedDict()
    for bb_name, triple_dict in succs_cfg.items():
        out[bb_name] = {INSTRS: triple_dict[INSTRS],
                        PREDS: preds_cfg[bb_name], SUCCS: triple_dict[SUCCS]}
    return out


def delete_from_cfg(basic_block_name, cfg):
    """
    Deletes all metadata of basic_block_name from the cfg
    """
    predecessors = cfg[basic_block_name][PREDS]
    successors = cfg[basic_block_name][SUCCS]

    del cfg[basic_block_name]

    for pred in predecessors:
        succ_of_pred = deepcopy(cfg[pred][SUCCS])
        succ_of_pred = list(set(succ_of_pred).difference({basic_block_name}))
        for succ in successors:
            succ_of_pred.append(succ)
        cfg[pred][SUCCS] = succ_of_pred

    for succ in successors:
        pred_of_succ = deepcopy(cfg[succ][PREDS])
        pred_of_succ = list(set(pred_of_succ).difference({basic_block_name}))
        for pred in predecessors:
            pred_of_succ.append(pred)
        cfg[succ][PREDS] = pred_of_succ


def coalesce_function(function):
    """
    Perform Coalescing of CFG Blocks

    Consecutive Blocks of a CFG, separated only by a jump, will be joined together
    In particular, remove instructions such as:
    jmp <.next>;
    <.next>:

    into no jump no label
    """
    final_instrs = []
    prev_instr = None
    for instr in function[INSTRS]:
        if is_label(instr) and prev_instr != None and is_jmp(prev_instr) and instr[LABEL] == prev_instr[LABELS][0]:
            assert len(final_instrs) >= 1
            assert final_instrs[-1] == prev_instr
            final_instrs.pop()

            # check label is used or not
            label_used = False
            for other_instr in function[INSTRS]:
                # compare id's as comparing directly on instruction only compares fields of instruction, as instructions are implemented as dictionaries
                if id(other_instr) != id(prev_instr) and is_jmp(other_instr):
                    if instr[LABEL] in other_instr[LABELS]:
                        label_used = True
                elif is_br(other_instr):
                    if instr[LABEL] in other_instr[LABELS]:
                        label_used = True

            # only add label if the label is used
            if label_used:
                final_instrs.append(instr)
        else:
            final_instrs.append(instr)
        prev_instr = instr

    function[INSTRS] = final_instrs
    return final_instrs


def coalesce_prog(prog):
    for func in prog[FUNCTIONS]:
        coalesce_function(func)
    return prog


def insert_into_cfg(new_header, backnodes, succ, cfg):
    assert type(new_header) == str
    assert type(succ) == str
    assert type(cfg) == OrderedDict

    # find all predecessors of succ
    predecessors = cfg[succ][PREDS]

    # add new_header to cfg
    # make its successor be succ
    # make its predecessors be the preds of succ
    safe_ret_label = {LABEL: f"safe.return.{new_header}"}
    new_ret = {OP: RET}
    new_label = {LABEL: new_header}
    new_jmp = {OP: JMP, LABELS: [succ]}
    cfg[new_header] = {PREDS: predecessors,
                       INSTRS: [safe_ret_label, new_ret, new_label, new_jmp], SUCCS: [succ]}

    # change succ's predecessor to new_header
    cfg[succ][PREDS] = [new_header]

    # change all predecessors of succ to point at new_header
    for pred in predecessors:
        # ignore backedge branch/jumps back to loop header
        if pred in backnodes:
            continue
        pred_successors = cfg[pred][SUCCS]
        new_successors = [new_header]
        for s in pred_successors:
            if s != succ:
                new_successors.append(new_header)
        cfg[pred][SUCCS] = new_successors
        new_jmp = {OP: JMP, LABELS: [new_header]}
        cfg[pred][INSTRS].append(new_jmp)


def join_cfg(cfg):
    assert type(cfg) == OrderedDict

    new_instrs = []
    for label, bb_dict in cfg.items():
        bb = bb_dict[INSTRS]
        if len(bb) != 0 and 'label' not in bb[0]:
            new_instrs.append({'label': label})
        elif len(bb) == 0:
            new_instrs.append({'label': label})
        for instr in bb:
            new_instrs.append(instr)
    return new_instrs


def reverse_cfg(cfg):
    new_cfg = OrderedDict()
    for basic_block in cfg:
        new_dict = {SUCCS: deepcopy(cfg[basic_block][PREDS]),
                    INSTRS: cfg[basic_block][INSTRS],
                    PREDS: deepcopy(cfg[basic_block][SUCCS])}
        new_cfg[basic_block] = new_dict
    return new_cfg


def add_unique_exit_to_cfg(cfg, exit_name):
    preds_of_exit = []
    for basic_block in cfg:
        if cfg[basic_block][SUCCS] == []:
            preds_of_exit.append(basic_block)
            cfg[basic_block][SUCCS].append(exit_name)

    exit_dict = {SUCCS: [], INSTRS: [], PREDS: preds_of_exit}
    cfg[exit_name] = exit_dict
    return cfg


def form_cfg_w_blocks(func):
    return get_cfg_w_blocks(form_block_dict(form_blocks(func['instrs'])))


def insert_into_cfg_w_blocks(block_name, block_instrs, preds, succs, cfg):
    """
    Inserts into a CFG w Pred/Succ/Blocks at the end, with the given block name and block instrs 
    block_name must not be in CFG, e.g. it must be unique
    No safety returns added
    """
    cfg[block_name] = {}
    cfg[block_name][INSTRS] = block_instrs
    cfg[block_name][PREDS] = preds
    cfg[block_name][SUCCS] = succs
    return cfg


def form_cfg(func):
    """
    Takes a Function Body and turns it into a CFG, labeled with successors only 
    (predecessors not included)
    """
    return get_cfg(block_map(form_blocks(func['instrs'])))


def get_graphviz(func, cfg, name2block):
    print('digraph {} {{'.format(func['name']))
    for name in name2block:
        print('  {};'.format(name))
    for name, succs in cfg.items():
        for succ in succs:
            print('  {} -> {};'.format(name, succ))
    print('}')


def main():
    prog = json.load(sys.stdin)
    for func in prog["functions"]:
        name2block = block_map(form_blocks(func['instrs']))
        cfg = get_cfg(name2block)
        get_graphviz(func, cfg, name2block)


if __name__ == "__main__":
    main()
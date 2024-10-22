import sys
import json
import click
from collections import OrderedDict
from copy import deepcopy

from cfg import form_cfg_succs_preds, PREDS, SUCCS
from bril_core_constants import NAME


NO_PREDECESSOR_HEADER = "no.predecessor.header"


def big_intersection(lst):
    assert type(lst) == list
    if lst == []:
        return set()
    out = lst[0]
    assert type(out) == set
    for e in lst:
        out = out.intersection(e)
    return out


def dfs(cfg, current, visited):
    """
    Finds all reachable vertices in cfg, from current vertex
    start vertex must be in cfg
    """
    assert type(visited) == set
    assert current in cfg

    visited.add(current)
    for n in cfg[current][SUCCS]:
        if n not in visited:
            result = dfs(cfg, n, visited)
            visited = visited.union(result)
    return visited


def paths_dfs(node, visited_nodes, prefix_paths, cfg, terminating_node):
    visited_nodes.add(node)
    if prefix_paths == []:
        prefix_paths = [[node]]
    else:
        for pp in prefix_paths:
            pp.append(node)
    if node == terminating_node:
        return prefix_paths
    if cfg[node][SUCCS] == []:
        return []
    paths = []
    for next_node in cfg[node][SUCCS]:
        if next_node not in visited_nodes:
            paths += paths_dfs(next_node, visited_nodes,
                               prefix_paths, cfg, terminating_node)
    return paths


def check_domination(domby, cfg, entry=None):
    if entry == None:
        entry = list(cfg.keys())[0]
    for b in domby:
        paths = paths_dfs(entry, set(), [], cfg, b)
        for a in domby[b]:
            for pp in paths:
                if a not in pp:
                    raise RuntimeError(
                        f"Path {', '.join(pp)} from {b} to {entry} does not contain {a};\n Therefore {a} does not dominate {b}.")
    return domby


def get_dominators_helper(cfg, entry=None):
    """
    Calculates Dominators for a function

    Gives the dominators as a dictionary, e.g. BasicBlock::[Dominators of BasicBlock]
    """
    if entry == None:
        entry = list(cfg.keys())[0]

    # set up before iteration
    # NOTE: I am not sure if this is completely correct, but it *SEEMS* to handle
    # unreachable blocks. Otherwise, some SCC algorithm is probably needed
    domby = OrderedDict()
    reachable_blocks = set()
    if len(cfg) >= 1:
        reachable_blocks = dfs(cfg, entry, set())
    for bb_name in cfg:
        if bb_name == entry:
            domby[bb_name] = {bb_name}
        elif bb_name in reachable_blocks:
            domby[bb_name] = reachable_blocks

    # iterate to convergence
    dom_changed = True
    while dom_changed:
        old_dom = deepcopy(domby)

        for bb_name in [name for name in cfg if name in reachable_blocks]:
            dom_predecessors = [domby[p]
                                for p in cfg[bb_name][PREDS] if p in reachable_blocks]

            if bb_name == entry:
                continue
            intersection = big_intersection(dom_predecessors)
            domby[bb_name] = {bb_name}.union(intersection)

        dom_changed = old_dom != domby

    # for unreachable blocks, for the purpose of ssa, we say they are dominated by entry
    # actually they are domijnated by all nodes
    for node in cfg:
        if node not in reachable_blocks:
            domby[node] = {entry}

    dom = OrderedDict()
    for bb in cfg:
        dominates = set()
        for otherbb, dominatedby in domby.items():
            if bb in dominatedby:
                dominates.add(otherbb)
        dom[bb] = list(dominates)

    domby = check_domination(domby, cfg, entry)
    return dom, domby


def get_dominators(func):
    assert type(func) == dict
    func_instructions = func["instrs"]
    cfg = form_cfg_succs_preds(func_instructions)
    return get_dominators_helper(cfg)


def get_dominators_w_cfg(cfg, entry):
    return get_dominators_helper(cfg, entry)


def dominators(prog):
    for func in prog["functions"]:
        _, domby = get_dominators(func)
        # for bb_name, dominates in dom.items():
        #     print(f"\t{bb_name} dominates:\t[{', '.join(sorted(dominates))}]")
        for bb_name, dominated in domby.items():
            print(
                f"\t{bb_name} is dominated by:\t[{', '.join(sorted(dominated))}]")


def get_strict_dominators(dom):
    """
    Get strict dominators, e.g. dominators of a node n, excluding n itself
    """
    strict_dom = OrderedDict()
    for bb_name, doms in dom.items():
        new_doms = deepcopy(doms)
        new_doms = set(new_doms).difference({bb_name})
        strict_dom[bb_name] = list(new_doms)
    return strict_dom


def get_immediate_dominators(strict_dom):
    """
    For a vertex v, get the unique vertex u that strictly dominates v,
    but that u does not strictly dominate any other vertex u' that also
    strictly dominates v.

    If there is no such vertex, then the vertex is the entry vertex,
    and it is immediately dominated by itself,

    (Kinda like a LUB for strict dominators)
    """
    imm_dom = OrderedDict()
    for node_A, node_A_strict in strict_dom.items():
        immediate = []
        for node_B in node_A_strict:
            can_add = True
            for node_C in node_A_strict:
                if node_B != node_C:
                    node_C_strict = strict_dom[node_C]
                    if node_B in node_C_strict:
                        can_add = False
                        break
            if can_add:
                # B immediately dominates A
                immediate.append(node_B)

        if immediate != []:
            assert len(immediate) == 1
            imm_dom[node_A] = immediate[0]
        else:
            # special case: entry is immediately dominated by itself
            imm_dom[node_A] = node_A
    return imm_dom


def build_dominance_tree_helper(domby):
    strict_dom = get_strict_dominators(domby)
    imm_dom = get_immediate_dominators(strict_dom)
    nodes = OrderedDict()
    tree = OrderedDict()
    for bb, dom_obj in imm_dom.items():
        nodes[bb] = None
        if bb != dom_obj:
            if dom_obj not in tree:
                tree[dom_obj] = [bb]
            else:
                tree[dom_obj].append(bb)
            if bb not in tree:
                tree[bb] = []
        else:
            # entry point:
            tree[bb] = []
    return tree, nodes


def build_dominance_tree(func):
    _, domby = get_dominators(func)
    return build_dominance_tree_helper(domby)


def build_dominance_tree_w_cfg(cfg, entry=None):
    _, domby = get_dominators_w_cfg(cfg, entry)
    return build_dominance_tree_helper(domby)


def get_tree_graph(tree, func, nodes):
    print('digraph {} {{'.format(func['name']))
    for name in nodes:
        print('  {};'.format(name))
    for name, succs in tree.items():
        for succ in succs:
            print('  {} -> {};'.format(name, succ))
    print('}')


def dominance_tree(prog):
    for func in prog["functions"]:
        tree, nodes = build_dominance_tree(func)
        get_tree_graph(tree, func, nodes)


def check_dominance_frontier(df, strict_dom, dom, cfg):
    for nodeA in df:
        strict_dom_A = strict_dom[nodeA]
        for nodeB in df[nodeA]:
            assert nodeB not in strict_dom_A
            predBs = cfg[nodeB][PREDS]
            exists = False
            for p in predBs:
                if p in dom[nodeA]:
                    exists = True
            if not exists:
                assert False
    return df


def build_dominance_frontier_helper(cfg, dom, strict_dom):
    """
    The dominator frontier is a set of nodes defined for every node (basic block)
    Consider a basic block A. The dominance frontier of A contains a node B
    iff A does not strictly dominate B but A dominiates some predecessor of B.
    """
    out = OrderedDict()
    for nodeA in cfg:
        nodeA_dominance_frontier = set()
        for nodeB in cfg:
            if nodeB not in strict_dom[nodeA]:
                for nodeC in cfg[nodeB][PREDS]:
                    if nodeC in dom[nodeA]:
                        nodeA_dominance_frontier.add(nodeB)
                        break
        out[nodeA] = list(nodeA_dominance_frontier)
    check_dominance_frontier(out, strict_dom, dom, cfg)
    return out


def build_dominance_frontier(func):
    func_instructions = func["instrs"]
    cfg = form_cfg_succs_preds(func_instructions)
    dom, _ = get_dominators(func)
    strict_dom = get_strict_dominators(dom)
    return build_dominance_frontier_helper(cfg, dom, strict_dom)


def build_dominance_frontier_w_cfg(cfg, entry):
    """
    CFG version of build_dominance_frontier
    """
    dom, _ = get_dominators_w_cfg(cfg, entry)
    strict_dom = get_strict_dominators(dom)
    return build_dominance_frontier_helper(cfg, dom, strict_dom)


def dominance_frontier(prog):
    for func in prog["functions"]:
        frontier = build_dominance_frontier(func)
        for bb_name, dominated in frontier.items():
            print(f"\t{bb_name}:\t[{', '.join(sorted(dominated))}]")


def get_backedges_helper(cfg, dom):
    backedges = []
    for A in cfg:
        for B in cfg:
            if B in cfg[A][SUCCS] and A in dom[B]:
                backedges.append((A, B))
    return backedges


def get_backedges(func):
    func_instructions = func["instrs"]
    cfg = form_cfg_succs_preds(func_instructions)
    dom, _ = get_dominators(func)
    return get_backedges_helper(cfg, dom)


def get_backedges_w_cfg(cfg, entry):
    dom, _ = get_dominators_w_cfg(cfg, entry)
    return get_backedges_helper(cfg, dom)


def backedges(prog):
    for func in prog["functions"]:
        backedges = get_backedges(func)
        print(func[NAME])
        for A, B in backedges:
            print(f"\tEdge from {A}->{B}, where {B} dominates {A}.")


def get_natural_loops(func):
    func_instructions = func["instrs"]
    cfg = form_cfg_succs_preds(func_instructions)
    backedges = get_backedges(func)

    loops = []

    for (A, B) in backedges:
        natural_loop = [A, B]

        continue_checking = True
        while continue_checking:
            new_natural_loop = deepcopy(natural_loop)
            for v in natural_loop:
                if v != B:
                    v_preds = cfg[v][PREDS]
                    for p in v_preds:
                        if p not in natural_loop:
                            new_natural_loop.append(p)

            if new_natural_loop == natural_loop:
                continue_checking = False
            natural_loop = new_natural_loop

        # check only 1 entrance to natural loop is via B, the loop header.
        is_natural = True
        for node in [n for n in cfg if n not in natural_loop]:
            successors = cfg[node][SUCCS]
            for s in successors:
                if s != B and s in natural_loop:
                    is_natural = False

        if is_natural:
            # get exits for natural loop
            exits = []
            for node in natural_loop:
                for s in cfg[node][SUCCS]:
                    if s not in natural_loop:
                        exits.append((node, s))

            header = B
            loops.append((natural_loop, (A, B), header, exits))

    return loops


def natural_loops(prog):
    for func in prog["functions"]:
        natural_loops = get_natural_loops(func)
        print(func[NAME])
        for loop, _, _, _ in natural_loops:
            print(f"\tNatural Loop: {{ {', '.join(loop)} }}")


@click.command()
@click.option('--dominator', default=False, help='Print Dominators.')
@click.option('--tree', default=False, help='Print Dominator Tree.')
@click.option('--frontier', default=False, help='Print Domination Frontier.')
@click.option('--back', default=False, help='Pretty Back Edges of Program.')
@click.option('--loops', default=False, help='Pretty Natural Loops of Program.')
@click.option('--pretty-print', default=False, help='Pretty Print Original Program.')
def main(dominator, tree, frontier, back, loops, pretty_print):
    prog = json.load(sys.stdin)
    if pretty_print:
        print(json.dumps(prog, indent=4, sort_keys=True))
    if dominator:
        print("Dominators")
        dominators(prog)
    if tree:
        print("Dominator Tree")
        dominance_tree(prog)
    if frontier:
        print("Dominance Frontier")
        dominance_frontier(prog)
    if back:
        print("Back Edges")
        backedges(prog)
    if loops:
        print("Natural Loops")
        natural_loops(prog)


if __name__ == "__main__":
    main()
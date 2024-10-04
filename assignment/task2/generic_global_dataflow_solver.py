import sys
import json
from collections import deque
from abc import ABC, abstractmethod
from form_blocks import form_blocks
from util import flatten

class DataflowAnalysis(ABC):
    def __init__(self, cfg, blocks, direction='forward'):
        self.cfg = cfg
        self.blocks = blocks  # Dictionary mapping labels to blocks
        self.direction = direction  # 'forward' or 'backward'
        self.in_fact = {}
        self.out_fact = {}
        self.init_facts()

    def init_facts(self):
        for label in self.cfg.keys():
            self.in_fact[label] = self.initial_fact()
            self.out_fact[label] = self.initial_fact()

        if self.direction == 'forward':
            entry_label = list(self.cfg.keys())[0]
            self.in_fact[entry_label] = self.entry_fact()
        else:
            exit_labels = [label for label, succs in self.cfg.items() if not succs]
            for label in exit_labels:
                self.out_fact[label] = self.entry_fact()

    @abstractmethod
    def initial_fact(self):
        pass

    @abstractmethod
    def entry_fact(self):
        pass

    @abstractmethod
    def meet(self, facts):
        pass

    @abstractmethod
    def transfer(self, block, input_fact):
        pass

    def analyze(self):
        if self.direction == 'forward':
            worklist = deque(self.cfg.keys())
        else:
            worklist = deque(reversed(list(self.cfg.keys())))

        while worklist:
            label = worklist.popleft()
            block = self.blocks[label]

            if self.direction == 'forward':
                # Compute in_fact[label]
                preds = self.predecessors(label)
                if preds:
                    in_fact = self.meet([self.out_fact[pred] for pred in preds])
                else:
                    in_fact = self.in_fact[label]

                # Compute out_fact[label]
                out_fact = self.transfer(block, in_fact)

                if out_fact != self.out_fact[label]:
                    self.out_fact[label] = out_fact
                    self.in_fact[label] = in_fact
                    for succ in self.cfg[label]:
                        if succ not in worklist:
                            worklist.append(succ)
            else:
                # Backward analysis
                # Compute out_fact[label]
                succs = self.cfg[label]
                if succs:
                    out_fact = self.meet([self.in_fact[succ] for succ in succs])
                else:
                    out_fact = self.out_fact[label]

                # Compute in_fact[label]
                in_fact = self.transfer(block, out_fact)

                if in_fact != self.in_fact[label]:
                    self.in_fact[label] = in_fact
                    self.out_fact[label] = out_fact
                    for pred in self.predecessors(label):
                        if pred not in worklist:
                            worklist.append(pred)

    def predecessors(self, label):
        """Return the predecessors of a label in the CFG."""
        preds = []
        for node, succs in self.cfg.items():
            if label in succs:
                preds.append(node)
        return preds

class AvailableExpressionsAnalysis(DataflowAnalysis):
    def initial_fact(self):
        return set()

    def entry_fact(self):
        return set()

    def meet(self, facts):
        return set.intersection(*facts) if facts else set()

    def transfer(self, block, in_fact):
        out_fact = in_fact.copy()
        for instr in block:
            op = instr.get('op')
            dest = instr.get('dest')
            args = instr.get('args', [])

            if not op:
                continue

            if is_side_effecting(op):
                affected_vars = set()
                if dest:
                    affected_vars.add(dest)
                affected_vars.update(args)
                out_fact = {e for e in out_fact if not (set(e[1]) & affected_vars)}
                continue


            if dest and is_pure(op):
                expr = self.create_expr(op, args)
                out_fact.add(expr)
                out_fact = {e for e in out_fact if dest not in e[1]}
            else:
                if dest:
                    out_fact = {e for e in out_fact if dest not in e[1]}
        return out_fact

    def create_expr(self, op, args):
        if op in ['add', 'mul', 'and', 'or', 'eq', 'fadd', 'fmul']:
            args = sorted(args)
        return (op, tuple(args))

def is_pure(op):
    """Check if an operation is pure (no side effects)."""
    pure_ops = [
        'const', 'id',
        'add', 'sub', 'mul', 'div',
        'fadd', 'fsub', 'fmul', 'fdiv',
        'eq', 'lt', 'gt', 'le', 'ge',
        'not', 'and', 'or',
        'call'  
    ]
    return op in pure_ops

def is_side_effecting(op):
    """Check if an operation may have side effects."""
    side_effecting_ops = [
        'print', 'jmp', 'br', 'ret',
        'alloc', 'free', 'store', 'load', 'ptradd', 'ptrsub',
        'call',  
        'phi'    
    ]
    return op in side_effecting_ops

def eliminate_common_subexpressions(func):
    """Perform common subexpression elimination on a function."""
    blocks_list = list(form_blocks(func['instrs']))
    cfg, label2block = build_cfg(blocks_list)

    analysis = AvailableExpressionsAnalysis(cfg, label2block, direction='forward')
    analysis.analyze()

    expr_to_var = {}

    for label in cfg.keys():
        block = label2block[label]
        available_exprs = analysis.in_fact[label].copy()
        new_block = []
        for instr in block:
            op = instr.get('op')
            dest = instr.get('dest')
            args = instr.get('args', [])

            if not op:
                new_block.append(instr)
                continue

            if is_side_effecting(op):
                new_block.append(instr)
                affected_vars = set()
                if dest:
                    affected_vars.add(dest)
                affected_vars.update(args)
                expr_to_var = {e: v for e, v in expr_to_var.items() if not (set(e[1]) & affected_vars)}
                continue

            if dest and is_pure(op):
                expr = analysis.create_expr(op, args)
                if expr in available_exprs and expr in expr_to_var:
                    prev_var = expr_to_var[expr]
                    new_instr = {
                        'op': 'id',
                        'type': instr['type'],
                        'dest': dest,
                        'args': [prev_var]
                    }
                    instr = new_instr
                else:
                    expr_to_var[expr] = dest
                    available_exprs.add(expr)
                expr_to_var = {e: v for e, v in expr_to_var.items() if dest != v}
                available_exprs = {e for e in available_exprs if dest not in e[1]}
            else:
                if dest:
                    expr_to_var = {e: v for e, v in expr_to_var.items() if dest != v}
                    available_exprs = {e for e in available_exprs if dest not in e[1]}
            new_block.append(instr)
        label2block[label] = new_block

    func['instrs'] = flatten([label2block[label] for label in cfg.keys()])

def build_cfg(blocks):
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
    return cfg, label2block

def main():
    prog = json.load(sys.stdin)

    for func in prog['functions']:
        eliminate_common_subexpressions(func)

    json.dump(prog, sys.stdout, indent=2)

if __name__ == "__main__":
    main()
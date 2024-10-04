import sys
import json
from collections import defaultdict, deque
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
        """Initialize in_fact and out_fact dictionaries."""
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
        """Return the initial dataflow fact."""
        pass

    @abstractmethod
    def entry_fact(self):
        """Return the dataflow fact at the entry (or exit for backward analysis)."""
        pass

    @abstractmethod
    def meet(self, facts):
        """Meet operator to combine dataflow facts from multiple paths."""
        pass

    @abstractmethod
    def transfer(self, block, input_fact):
        """Transfer function for a block."""
        pass

    def analyze(self):
        """Perform the dataflow analysis using a worklist algorithm."""
        # Initialize worklist
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

# Implementing Constant Propagation using Reaching Definitions
class ConstantPropagationAnalysis(DataflowAnalysis):
    def initial_fact(self):
        # Start with all variables having 'Top' value (unknown)
        return {}

    def entry_fact(self):
        # At the entry, variables have 'Top' value
        return {}

    def meet(self, facts):
        # The meet operator for constants is intersection
        result = {}
        keys = set().union(*[fact.keys() for fact in facts])
        for key in keys:
            values = {fact.get(key, 'Top') for fact in facts}
            if len(values) == 1:
                result[key] = values.pop()
            else:
                # If the variable has different values along paths, it's 'Bottom' (non-constant)
                result[key] = 'Bottom'
        return result

    def transfer(self, block, in_fact):
        out_fact = in_fact.copy()
        for instr in block:
            if 'dest' in instr:
                dest = instr['dest']
                op = instr.get('op')
                if op == 'const':
                    # Assign constant value
                    out_fact[dest] = instr['value']
                elif op in ['add', 'mul', 'sub', 'div', 'eq', 'lt', 'gt', 'le', 'ge', 'not', 'and', 'or']:
                    args = instr.get('args', [])
                    arg_values = [out_fact.get(arg, 'Top') for arg in args]
                    if all(isinstance(val, int) for val in arg_values):
                        try:
                            value = evaluate(instr['op'], arg_values)
                            out_fact[dest] = value
                        except ZeroDivisionError:
                            out_fact[dest] = 'Bottom'
                    else:
                        out_fact[dest] = 'Bottom'
                else:
                    # For other ops, we assume the variable becomes non-constant
                    out_fact[dest] = 'Bottom'
            else:
                # No destination, do nothing
                pass
        return out_fact

def evaluate(op, args):
    """Evaluate an operation with constant arguments."""
    if op == 'add':
        return args[0] + args[1]
    elif op == 'sub':
        return args[0] - args[1]
    elif op == 'mul':
        return args[0] * args[1]
    elif op == 'div':
        return args[0] // args[1]  # Integer division
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

# Function to build the Control Flow Graph (CFG)
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
                # Fall through to the next block
                if idx + 1 < len(blocks):
                    cfg[label].append(labels[idx + 1])
        else:
            if idx + 1 < len(blocks):
                cfg[label].append(labels[idx + 1])
    return cfg, label2block

def perform_constant_propagation(func):
    """Perform constant propagation on a function."""
    blocks_list = list(form_blocks(func['instrs']))
    cfg, label2block = build_cfg(blocks_list)

    # Initialize Constant Propagation Analysis
    analysis = ConstantPropagationAnalysis(cfg, label2block, direction='forward')
    analysis.analyze()

    # Replace variables with constants where possible
    for label in cfg.keys():
        block = label2block[label]
        constants = analysis.in_fact[label]
        new_block = []
        for instr in block:
            if 'op' not in instr:
                new_block.append(instr)
                continue

            if 'dest' in instr:
                dest = instr['dest']
            else:
                dest = None

            op = instr.get('op')
            args = instr.get('args', [])
            arg_values = [constants.get(arg, arg) for arg in args]

            # Replace arguments with constants where possible
            new_args = []
            for val in arg_values:
                if isinstance(val, int):
                    new_args.append(val)
                else:
                    new_args.append(val)

            instr['args'] = [str(arg) if isinstance(arg, int) else arg for arg in new_args]

            # If all arguments are constants, try to evaluate the instruction
            if op in ['add', 'sub', 'mul', 'div', 'eq', 'lt', 'gt', 'le', 'ge', 'and', 'or', 'not']:
                if all(isinstance(val, int) for val in arg_values):
                    try:
                        result = evaluate(op, arg_values)
                        # Replace instruction with const
                        new_instr = {
                            'op': 'const',
                            'dest': dest,
                            'type': instr['type'],
                            'value': result
                        }
                        instr = new_instr
                    except ZeroDivisionError:
                        pass  # Keep the original instruction if division by zero
            new_block.append(instr)
        label2block[label] = new_block

    # Update the function's instructions
    func['instrs'] = flatten([label2block[label] for label in cfg.keys()])

def main():
    prog = json.load(sys.stdin)

    for func in prog['functions']:
        perform_constant_propagation(func)
        # Optionally, you can run dead code elimination after constant propagation
        # eliminate_dead_code(func)

    json.dump(prog, sys.stdout, indent=2)

if __name__ == "__main__":
    main()
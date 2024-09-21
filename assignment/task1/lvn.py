import sys
import json

def lvn_basic_block(block):
    var2num = {}    # Maps variable names to value numbers
    num2var = {}    # Maps value numbers to variable names (first occurrence)
    num2val = {}    # Maps value numbers to their expressions or constants
    num2const = {}  # Maps value numbers to constant values
    next_num = 0    # Next available value number
    optimized_block = []

    for instr in block:
        if 'op' in instr:
            op = instr['op']
            dest = instr.get('dest')
            args = instr.get('args', [])
            arg_nums = []
            arg_consts = []

            for arg in args:
                if arg in var2num:
                    arg_num = var2num[arg]
                else:
                    arg_num = next_num
                    var2num[arg] = arg_num
                    num2var[arg_num] = arg
                    num2val[arg_num] = ('var', arg)
                    next_num += 1
                arg_nums.append(arg_num)
                arg_consts.append(num2const.get(arg_num))

            if op == 'const':
                value = instr['value']
                num = next_num
                var2num[dest] = num
                num2var[num] = dest
                num2val[num] = ('const', value)
                num2const[num] = value
                next_num += 1
                optimized_block.append(instr)
            elif op in ['add', 'sub', 'mul', 'div']:
                if op in ['add', 'mul']:
                    sorted_args = sorted(zip(arg_nums, arg_consts), key=lambda x: x[0])
                    arg_nums = [num for num, const in sorted_args]
                    arg_consts = [const for num, const in sorted_args]
                if all(const is not None for const in arg_consts):
                    left_const, right_const = arg_consts
                    try:
                        if op == 'add':
                            result = left_const + right_const
                        elif op == 'sub':
                            result = left_const - right_const
                        elif op == 'mul':
                            result = left_const * right_const
                        elif op == 'div':
                            result = left_const // right_const
                        num = next_num
                        var2num[dest] = num
                        num2var[num] = dest
                        num2val[num] = ('const', result)
                        num2const[num] = result
                        next_num += 1
                        optimized_block.append({
                            'op': 'const',
                            'dest': dest,
                            'type': instr['type'],
                            'value': result
                        })
                    except ZeroDivisionError:
                        num = next_num
                        var2num[dest] = num
                        num2var[num] = dest
                        num2val[num] = (op, tuple(arg_nums))
                        next_num += 1
                        optimized_block.append(instr)
                else:
                    key = (op, tuple(arg_nums))
                    existing_num = None
                    for num, val in num2val.items():
                        if val == key:
                            existing_num = num
                            break
                    if existing_num is not None:
                        existing_var = num2var[existing_num]
                        var2num[dest] = existing_num
                        optimized_block.append({
                            'op': 'id',
                            'args': [existing_var],
                            'dest': dest,
                            'type': instr['type']
                        })
                    else:
                        num = next_num
                        var2num[dest] = num
                        num2var[num] = dest
                        num2val[num] = key
                        next_num += 1
                        optimized_block.append(instr)
            else:
                optimized_block.append(instr)
                if dest:
                    num = next_num
                    var2num[dest] = num
                    num2var[num] = dest
                    num2val[num] = (op, tuple(arg_nums))
                    next_num += 1
                    if op == 'id' and arg_consts[0] is not None:
                        num2const[num] = arg_consts[0]
        else:
            # Labels or annotations
            optimized_block.append(instr)
    return optimized_block

def lvn_function(func):
    new_instrs = []
    current_block = []

    for instr in func['instrs']:
        if 'label' in instr:
            if current_block:
                new_instrs.extend(lvn_basic_block(current_block))
                current_block = []
            new_instrs.append(instr)
        else:
            current_block.append(instr)

    if current_block:
        new_instrs.extend(lvn_basic_block(current_block))

    func['instrs'] = new_instrs
    return func

def main():
    prog = json.load(sys.stdin)

    for func in prog['functions']:
        lvn_function(func)

    json.dump(prog, sys.stdout, indent=2)

if __name__ == "__main__":
    main()

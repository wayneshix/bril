from bril_core_constants import *


def uses(instr1, instr2):
    """
    True iff instr1 directly uses instr2
    """
    assert type(instr1) == dict
    assert type(instr2) == dict
    if ARGS in instr1:
        args = instr1[ARGS]
        if DEST in instr2:
            dst = instr2[ARGS]
            return dst in args
    return False


def commutes(instr):
    return is_add(instr) or is_mul(instr) or is_and(instr) or is_or(instr) or is_eq(instr)


def has_dest(instr):
    assert type(instr) == dict
    return DEST in instr


def get_dest(instr):
    assert type(instr) == dict
    return instr[DEST]


def has_args(instr):
    assert type(instr) == dict
    return ARGS in instr


def get_args(instr):
    assert type(instr) == dict
    return instr[ARGS]


def is_int(instr):
    assert type(instr) == dict
    return TYPE in instr and instr[TYPE] == INT


def is_bool(instr):
    assert type(instr) == dict
    return TYPE in instr and instr[TYPE] == BOOL


def is_cmp(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] in COMP_OPS


def is_phi(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == PHI


def is_unop(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] in BRIL_UNOPS


def is_binop(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] in BRIL_BINOPS


def is_add(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == ADD


def is_sub(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == SUB


def is_mul(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == MUL


def is_div(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == DIV


def build_add(dest, arg1, arg2):
    assert type(dest) == str
    assert type(arg1) == str
    assert type(arg2) == str
    return {DEST: dest, TYPE: INT, OP: ADD, ARGS: [arg1, arg2]}


def build_sub(dest, arg1, arg2):
    assert type(dest) == str
    assert type(arg1) == str
    assert type(arg2) == str
    return {DEST: dest, TYPE: INT, OP: SUB, ARGS: [arg1, arg2]}


def build_mul(dest, arg1, arg2):
    assert type(dest) == str
    assert type(arg1) == str
    assert type(arg2) == str
    return {DEST: dest, TYPE: INT, OP: MUL, ARGS: [arg1, arg2]}


def build_div(dest, arg1, arg2):
    assert type(dest) == str
    assert type(arg1) == str
    assert type(arg2) == str
    return {DEST: dest, TYPE: INT, OP: DIV, ARGS: [arg1, arg2]}


def is_not(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == NOT


def build_eq(dest, arg):
    assert type(dest) == str
    assert type(arg) == str
    return {DEST: dest, TYPE: BOOL, OP: EQ, ARGS: [arg]}


def is_eq(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == EQ


def build_not(dest, arg):
    assert type(dest) == str
    assert type(arg) == str
    return {DEST: dest, TYPE: BOOL, OP: NOT, ARGS: [arg]}


def is_and(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == AND


def build_and(dest, arg1, arg2):
    assert type(dest) == str
    assert type(arg1) == str
    assert type(arg2) == str
    return {DEST: dest, TYPE: BOOL, OP: AND, ARGS: [arg1, arg2]}


def is_or(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == OR


def build_or(dest, arg1, arg2):
    assert type(dest) == str
    assert type(arg1) == str
    assert type(arg2) == str
    return {DEST: dest, TYPE: BOOL, OP: OR, ARGS: [arg1, arg2]}


def is_lt(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == LT


def build_lt(dest, arg1, arg2):
    assert type(dest) == str
    assert type(arg1) == str
    assert type(arg2) == str
    return {DEST: dest, TYPE: BOOL, OP: LT, ARGS: [arg1, arg2]}


def is_gt(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == GT


def build_gt(dest, arg1, arg2):
    assert type(dest) == str
    assert type(arg1) == str
    assert type(arg2) == str
    return {DEST: dest, TYPE: BOOL, OP: GT, ARGS: [arg1, arg2]}


def is_le(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == LE


def build_le(dest, arg1, arg2):
    assert type(dest) == str
    assert type(arg1) == str
    assert type(arg2) == str
    return {DEST: dest, TYPE: BOOL, OP: LE, ARGS: [arg1, arg2]}


def is_ge(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == GE


def build_ge(dest, arg1, arg2):
    assert type(dest) == str
    assert type(arg1) == str
    assert type(arg2) == str
    return {DEST: dest, TYPE: BOOL, OP: GE, ARGS: [arg1, arg2]}


def is_const(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == CONST


def build_const(dest, typ, value):
    assert typ in BRIL_CORE_TYPES
    assert type(dest) == str
    return {DEST: dest, OP: CONST, TYPE: typ, VALUE: value}


def is_id(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == ID


def build_id(dest, typ, arg):
    assert type(dest) == str
    assert type(arg) == str
    assert type(typ) == str or type(typ) == dict
    return {DEST: dest, TYPE: typ, OP: ID, ARGS: [arg]}


def is_print(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == PRINT


def build_print(arg):
    assert type(arg) == str
    return {OP: PRINT, ARGS: [arg]}


def is_io(instr):
    return is_print(instr)


def is_call(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == CALL


def build_call(dest, args, func, typ):
    assert type(dest) == str
    assert type(args) == list
    for a in args:
        assert type(a) == str
    assert type(func) == str
    assert type(typ) == str
    return {
        ARGS: args,
        DEST: dest,
        FUNCS: [func],
        OP: CALL,
        TYPE: typ
    }


def is_label(instr):
    assert type(instr) == dict
    return LABEL in instr


def build_label(name: str):
    return {LABEL: name}


def is_ret(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == RET


def build_void_ret():
    return {OP: RET, ARGS: []}


def build_int_ret(int_var: str):
    return {OP: RET, ARGS: [int_var], TYPE: INT}


def build_bool_ret(bool_var: str):
    return {OP: RET, ARGS: [bool_var], TYPE: BOOL}


def build_ret(var, typ):
    assert type(var) == str or var == None
    assert (type(typ) == str) or (type(typ) == dict) or typ == None
    if typ == None:
        return build_void_ret()
    return {OP: RET, ARGS: [var], TYPE: typ}


def is_nop(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == NOP


def build_nop(label):
    return {OP: NOP}


def is_jmp(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == JMP


def build_jmp(label):
    return {OP: JMP, LABELS: [label]}


def get_jmp_label(instr):
    assert is_jmp(instr)
    assert len(instr[LABELS]) == 1
    return instr[LABELS][0]


def is_br(instr):
    assert type(instr) == dict
    return OP in instr and instr[OP] == BR


def build_br(arg, label1, label2):
    return {OP: BR, ARGS: [arg], LABELS: [label1, label2]}


def get_br_labels(instr):
    assert is_br(instr)
    assert len(instr[LABELS]) == 2
    return instr[LABELS]


def is_terminator(instr):
    return is_jmp(instr) or is_br(instr) or is_ret(instr)


def has_side_effects(instr):
    return OP in instr and instr[OP] in SIDE_EFFECT_OPS


def postorder_traversal(node, tree):
    assert node in tree
    postorder = []
    for child in tree[node]:
        postorder += postorder_traversal(child, tree)
    postorder.append(node)
    return postorder


def reverse_postorder_traversal(node, tree):
    return list(reversed(postorder_traversal(node, tree)))


def lvn_value_is_const(lvn_value):
    assert type(lvn_value) == tuple
    assert len(lvn_value) >= 2
    return lvn_value[0] == CONST


def lvn_value_is_arg(lvn_value):
    assert type(lvn_value) == tuple
    assert len(lvn_value) >= 2
    return lvn_value[0] == ARGUMENT


def lvn_value_is_id(lvn_value):
    assert type(lvn_value) == tuple
    assert len(lvn_value) >= 2
    return lvn_value[0] == ID


def lvn_value_is_call(lvn_value):
    assert type(lvn_value) == tuple
    assert len(lvn_value) >= 2
    return lvn_value[0] == CALL


def get_lvn_value(curr_lvn_num, var2value_num, expr2value_num):
    if curr_lvn_num in var2value_num:
        value_num = var2value_num[curr_lvn_num]
        for expr, val in expr2value_num.items():
            if val == value_num:
                return expr
        raise RuntimeError("Value not bound in expr2value_num.")
    else:
        raise RuntimeError("LVN Num must be in var2value_num dictionary.")


def interpret_lvn_value(lvn_value, var2value_num, expr2value_num):
    assert type(lvn_value) == tuple
    assert len(lvn_value) >= 2
    if lvn_value_is_const(lvn_value):
        return lvn_value
    elif lvn_value_is_arg(lvn_value):
        return lvn_value
    elif lvn_value_is_call(lvn_value):
        return lvn_value
    new_args = []
    for arg_lvn_num in lvn_value[1:]:
        try:
            arg_lvn_value = get_lvn_value(
                arg_lvn_num, var2value_num, expr2value_num)
        except:
            # cannot simplify
            return lvn_value
        new_args.append(interpret_lvn_value(
            arg_lvn_value, var2value_num, expr2value_num))
    all_constants = True
    for a in new_args:
        if not lvn_value_is_const(a):
            all_constants = False

    op = lvn_value[0]
    # we disallow semi interpreted expressions, e.g. (ADD, const 1, 3)
    if not all_constants:
        # However, there are some other algebraic simplications possible.
        if op == EQ:
            if lvn_value[1] == lvn_value[2]:
                return (CONST, True)
        elif op == LT:
            if lvn_value[1] == lvn_value[2]:
                return (CONST, False)
        elif op == GT:
            if lvn_value[1] == lvn_value[2]:
                return (CONST, False)
        elif op == LE:
            if lvn_value[1] == lvn_value[2]:
                return (CONST, True)
        elif op == GE:
            if lvn_value[1] == lvn_value[2]:
                return (CONST, True)
        return lvn_value

    if op == CONST:
        raise RuntimeError(
            f"Constants are the base case: should be returned earlier.")
    elif op == ID:
        assert len(new_args) == 1
        return new_args[0]
    elif op == CALL:
        # unfortunately have to treat as uninterpreted function
        return lvn_value
    elif op == NOT:
        assert len(new_args) == 1
        (_, result, _) = new_args[0]
        return (CONST, not result, BOOL)
    elif op == AND:
        assert len(new_args) == 2
        (_, result1, _) = new_args[0]
        (_, result2, _) = new_args[1]
        return (CONST, result1 and result2, BOOL)
    elif op == OR:
        assert len(new_args) == 2
        (_, result1, _) = new_args[0]
        (_, result2, _) = new_args[1]
        return (CONST, result1 or result2, BOOL)
    elif op == EQ:
        assert len(new_args) == 2
        (_, result1, _) = new_args[0]
        (_, result2, _) = new_args[1]
        return (CONST, result1 == result2, BOOL)
    elif op == LE:
        assert len(new_args) == 2
        (_, result1, _) = new_args[0]
        (_, result2, _) = new_args[1]
        return (CONST, result1 <= result2, BOOL)
    elif op == GE:
        assert len(new_args) == 2
        (_, result1, _) = new_args[0]
        (_, result2, _) = new_args[1]
        return (CONST, result1 >= result2, BOOL)
    elif op == LT:
        assert len(new_args) == 2
        (_, result1, _) = new_args[0]
        (_, result2, _) = new_args[1]
        return (CONST, result1 < result2, BOOL)
    elif op == GT:
        assert len(new_args) == 2
        (_, result1, _) = new_args[0]
        (_, result2, _) = new_args[1]
        return (CONST, result1 > result2, BOOL)
    elif op == ADD:
        assert len(new_args) == 2
        (_, result1, _) = new_args[0]
        (_, result2, _) = new_args[1]
        return (CONST, result1 + result2, INT)
    elif op == SUB:
        assert len(new_args) == 2
        (_, result1, _) = new_args[0]
        (_, result2, _) = new_args[1]
        return (CONST, result1 - result2, INT)
    elif op == MUL:
        assert len(new_args) == 2
        (_, result1, _) = new_args[0]
        (_, result2, _) = new_args[1]
        return (CONST, result1 * result2, INT)
    elif op == DIV:
        assert len(new_args) == 2
        (_, result1, _) = new_args[0]
        (_, result2, _) = new_args[1]
        # bail on interpretation if divisor is 0
        if result2 == 0:
            return lvn_value
        return (CONST, result1 // result2, INT)
    raise RuntimeError(f"LVN Interpretation: Unmatched type {op}.")


def build_arg(name, typ):
    assert type(name) == str
    assert (type(typ) == str) or (type(typ) == dict)
    return {
        NAME: name,
        TYPE: typ,
    }


def build_func(name, args, typ, instrs):
    assert type(name) == str
    assert type(args) == list
    assert (type(typ) == str) or (type(typ) == dict) or typ == None
    assert type(instrs) == list
    if typ == None:
        return {
            NAME: name,
            ARGS: args,
            INSTRS: instrs,
        }
    return {
        NAME: name,
        ARGS: args,
        TYPE: typ,
        INSTRS: instrs,
    }


def build_program(functions):
    assert type(functions) == list
    return {
        FUNCTIONS: functions
    }


def isa_core_type(typ):
    assert (type(typ) == str) or (type(typ) == dict)
    if typ == INT:
        return True
    elif typ == BOOL:
        return True
    assert (type(typ) == dict)
    assert (len(typ) == 1)
    for _, v in typ.items():
        return isa_core_type(v)
    raise RuntimeError("Cannot Reach This Position in: isa_core_type")


def isa_int(typ):
    assert (type(typ) == str) or (type(typ) == dict)
    return typ == INT


def isa_bool(typ):
    assert (type(typ) == str) or (type(typ) == dict)
    return typ == BOOL
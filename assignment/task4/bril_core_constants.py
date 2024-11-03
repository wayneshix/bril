ARGS = "args"
DEST = "dest"
LABELS = "labels"
TYPE = "type"
OP = "op"
VALUE = "value"
LABEL = "label"
FUNCS = "funcs"
NAME = "name"


INT = "int"
BOOL = "bool"


CONST = "const"


ADD = "add"
SUB = "sub"
MUL = "mul"
DIV = "div"


EQ = "eq"
LT = "lt"
GT = "gt"
LE = "le"
GE = "ge"


NOT = "not"
AND = "and"
OR = "or"


JMP = "jmp"
BR = "br"
CALL = "call"
RET = "ret"


ID = "id"
PRINT = "print"
NOP = "nop"


PHI = "phi"


BRIL_BINOPS = [
    ADD, SUB, MUL, DIV,
    EQ, LT, GT, LE, GE,
    AND, OR,
]

COMP_OPS = [LT, GT, LE, GE, EQ]
LOGIC_OPS = [NOT, AND, OR]
BOOL_OPS = [NOT, AND, OR, LT, GT, LE, GE, EQ]
INT_OPS = [ADD, SUB, MUL, DIV]

BRIL_UNOPS = [NOT]


BRIL_CORE_OPS = [*BRIL_BINOPS, *BRIL_UNOPS]


BRIL_CORE_INSTRS = [
    *BRIL_BINOPS, *BRIL_UNOPS,
    JMP, BR, CALL, RET,
    ID, PRINT, NOP, PHI, CONST,
]

BRIL_COMMUTE_BINOPS = [
    ADD, MUL, AND, OR, EQ
]

BRIL_CORE_TYPES = [
    INT, BOOL
]

TERMINATORS = [JMP, BR, RET]

OP_TO_TYPE = {**{b: BOOL for b in BOOL_OPS}, **{i: INT for i in INT_OPS}}

SIDE_EFFECT_OPS = [
    PRINT, DIV
]


NUM_BINARY_ARGS = 2
NUM_UNARY_ARGS = 1


ARGUMENT = "argument"

INSTRS = "instrs"
FUNCTIONS = "functions"

MAIN = "main"
# Copyright 2020-2021 Turbonomic
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# libraries
import ast
from collections import OrderedDict
from decimal import Decimal
from functools import cmp_to_key
import math
from operator import itemgetter as ig


# all dunder names are implicitly excluded
INVALID_NAMES = [
  'callable',
  'class',
  'classmethod',
  'compile',
  'def',
  'del',
  'delattr',
  'dir',
  'eval',
  'exec',
  'execfile',
  'file',
  'filter',
  'getattr',
  'globals',
  'hasattr',
  'help',
  'id',
  'import',
  'input',
  'isinstance',
  'issubclass',
  'lambda',
  'locals',
  'object',
  'open',
  'print',
  'raw_input',
  'reload',
  'repr',
  'setattr',
  'type'
]

# we only need to specify expression classes, as the eval mode blocks statements
# classes already
INVALID_EXPR = [
    'Await',
    'GeneratorExp',
    'Lambda',
    'NamedExpr',
    'Yield',
    'YieldFrom'
]



class SafeNodeCheck(ast.NodeVisitor):
    """A wrapper for :class:`ast.NodeVisitor`.

    :py:class:`~_SafeEval` provides extension to :py:class:`ast.NodeVisitor` for
    the purpose of parsing custom domain specific languages required in client
    configurations. In practice this class should not be used directly.

    See Also:
        :py:class:`ast.NodeVisitor`.
    """
    def __init__(self):
        super().__init__()

        # block our unwanted expressions
        for expr in INVALID_EXPR:
            setattr(self, f'visit_{expr}', self.Invalid)

    def generic_visit(self, node):
        ast.NodeVisitor.generic_visit(self, node)

    def Invalid(self, node):
        raise SyntaxError('Invalid expression', ('', 1, 0, ''))

    def visit_Name(self, node):
        if node.id.lower() in INVALID_NAMES:
            self.Invalid(node)

        self.generic_visit(node)



def evaluate(exp):
    """Evaluates the expression ``exp`` and returns the results.

    Args:
        exp (str): Domain specific language expression to be evaluated.

    Returns:
        Expression result.
    """
    # squash object attribute reference attacks
    if '__' in exp:
        raise SyntaxError('Invalid expression', ('', 1, 0, ''))

    # eval mode permits a single expression only, and natively blocks statements
    # and assignments
    tree = ast.parse(exp, mode='eval')
    SafeNodeCheck().visit(tree)
    ast.fix_missing_locations(tree)
    cobj = compile(tree, '<ast>', 'eval')

    # Bandit nosec - false positive
    # All commands are first passed through SafeNodeCheck() which blocks unsafe
    # methods such as import, exec, etc as defined in INVALID_NAMES.
    #
    # The intention is to expclicitly allow mathematical syntax parsing, without
    # exposing other builtins, or permitting full scripts to run. Statements,
    # assignments, dunderes, and use of any excluded callables will return
    # SyntaxError.
    #
    # Note: user specified locals must not be passed to eval() as this would
    # present a risk of exposing addional builtins.
    return eval(cobj, {'math': math}, None) #nosec


def unit_cast(value, ufrom, uto, factor, unit_list, precision=False):
    """Generic unit conversion utility function.

    Unit conversions must utilize a scale relative to a constant factor, such as
    the metric system, or base 2 numbering used in computing.

    Args:
        value: Unit value to be converted
        ufrom (str): Scale unit converting from.
        uto (str): Scale unit converting to.
        factor: Scale factor to use in calculating the change.
        unit_list (list): The scale unit labels.
        precision (int, optional): rounding precision. If False no rounding is
            applied. (default: False)

    Returns:
        Converted unit value.
    """
    factor = Decimal(factor)
    value = Decimal(value)
    offset = unit_list.index(uto) - unit_list.index(ufrom)
    chg = Decimal(pow(factor, abs(offset)))

    res = value * chg if offset <= 0 else value * (Decimal(1)/chg)

    return round(res, precision) if precision else res


def mem_cast(value, unit='GB', factor=1024, src_unit='KB', precision=False):
    """Converts values using the binary (1024) system of units.

    ``mem_cast`` is a wrapper for ``unit_cast`` and supports memory sizes from
    Bytes (B) to Yottabytes (YB). Source values are expected to be supplied as
    raw values from Turbonomic, which defaults to KB. This behavior may be
    overridden using the ``src_unit`` argument.

    Args:
         value: Base memory unit value to convert.
         unit (str, optional): Destination unit to convert to (default: GB)
         factor (optional): Memory unit factor (default: 1024)
         src_unit (optional): Source unit to convert from (default: KB)
         precision (int, optional): rounding precision. If False no rounding is
            applied. (default: False)

    Returns:
        Converted unit value.

    Notes:
        This function may also be used for converting storage values. However,
        note that Turbonomic defaults to MB for storage values, instead of KB
        as it does with memory. ``src_unit`` must therefore be overridden to 'MB'.
    """
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']

    return unit_cast(value, src_unit.upper(), unit.upper(), factor, units,
                     precision)


def cpu_cast(value, unit='GHZ', factor=1000, src_unit='MZH', precision=False):
    """Converts values using the SI (1000) system of units.

    ``cpu_cast`` is a wrapper for ``unit_cast`` and supports cpu speeds from
    Hertz (HZ) to Petahertz (PHZ). Source values are expected to be supplied as
    raw values from Turbonomic, which dfaults to MHZ. This behavior may be
    overridden using the ``src_unit`` argument.

    Args:
         value: Base cpu unit value to convert.
         unit (str, optional): Destination unit to convert to (default: GHZ)
         factor (optional): Memory unit factor (default: 1024)
         src_unit (opitonal): Source unit to convert from (default: MHZ)
         precision (int, optional): rounding precision. If False no rounding is
            applied. (default: False)

    Returns:
        Converted unit value.
    """
    units = ['HZ', 'MHZ', 'GHZ', 'THZ', 'PHZ']

    return unit_cast(value, src_unit.upper(), unit.upper(), factor, units,
                     precision)


def multikeysort(items, columns):
    comparers = [
        ((ig(col[1:].strip()), -1) if col.startswith('-') else (ig(col.strip()), 1))
        for col in columns
    ]

    def cmp(x, y):
        return (x > y) - (x < y)

    def comparer(left, right):
        comparer_iter = (
            cmp(fn(left), fn(right)) * mult
            for fn, mult in comparers
        )
        return next((result for result in comparer_iter if result), 0)
    return sorted(items, key=cmp_to_key(comparer))

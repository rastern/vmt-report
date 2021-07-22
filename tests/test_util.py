#
# NOTES:
#
from decimal import Decimal
import pytest
import warnings

import vmtreport.util as vu


units = ['A', 'B', 'C', 'D', 'E', 'F']

unit_params = [
    pytest.param(10, 'A', 'B', 10, units, False, Decimal(1)),
    pytest.param(1, 'B', 'A', 10, units, False, Decimal(10)),
    pytest.param(25, 'A', 'D', 10, units, 4, round(Decimal(0.0250), 4)),
    pytest.param(21, 'D', 'A', 10, units, 1, Decimal(21000)),
    pytest.param(2115, 'A', 'D', 10, units, 2, round(Decimal(2.12), 2)),
]
mem_params = [
    pytest.param(2, 'KB', 'B', False, Decimal('2048')),
    pytest.param(2048, 'B', 'KB', False, Decimal('2')),
    pytest.param(256, 'B', 'KB', 2, Decimal('0.25')),
    pytest.param(256, 'B', 'KB', 1, Decimal('0.2'))
]
cpu_params = [
    pytest.param(2, 'MHZ', 'HZ', False, Decimal('2000')),
    pytest.param(2000000, 'HZ', 'GHZ', False, Decimal('2'))
]



@pytest.mark.parametrize('v,f,t,fac,lst,prc,out', unit_params)
def test_unitcast(v, f, t, fac, lst, prc, out):
    value = vu.unit_cast(v, f, t, fac, lst, prc)

    assert value == out

@pytest.mark.parametrize('v,f,t,p,out', mem_params)
def test_mem_cast(v, f, t, p, out):
    value = vu.mem_cast(v, t, src_unit=f, precision=p)

    assert value == out


@pytest.mark.parametrize('v,f,t,p,out', cpu_params)
def test_cpu_cast(v, f, t, p, out):
    value = vu.cpu_cast(v, t, src_unit=f, precision=p)

    assert value == out



def test_evaluate_len():
    assert vu.evaluate("2 + 3 * len('hello')") == 17


def test_evaluate_math():
    assert vu.evaluate('math.pow(2, 3)') == 8


def test_evaluate_block_names():
    with pytest.raises(SyntaxError):
        assert vu.evaluate("print('hello')") == 8


def test_evaluate_block_dangerous_builtins():
    with pytest.raises(NameError) as excinfo:
        import os
        assert vu.evaluate("os.system('')")


def test_evaluate_block_dunders():
    with pytest.raises(SyntaxError):
        assert vu.evaluate("__import__('os').system('')")


def test_evaluate_block_import():
    with pytest.raises(SyntaxError):
        assert vu.evaluate("import os\nos.systme('')")


def test_evaluate_block_assign():
    with pytest.raises(SyntaxError):
        assert vu.evaluate("a = 15")


def test_evaluate_block_loop():
    with pytest.raises(SyntaxError):
        assert vu.evaluate("for x in 100:\n\tx+5")


def test_evaluate_block_lambda():
    with pytest.raises(SyntaxError):
        assert vu.evaluate('lambda x: x + 1')


def test_evaluate_block_await():
    with pytest.raises(SyntaxError):
        assert vu.evaluate('await True')


def test_evaluate_block_dynamic_objects():
    # The code snippets will instantiate a new object dynamically by locating
    # the base funcion object and directly calling its constructor, ultimately
    # leading to a segfault.

    # 12 arg code() version - earlier versions of python
    v12 = """
    (lambda fc=(
        lambda n: [
            c for c in
                ().__class__.__bases__[0].__subclasses__()
                if c.__name__ == n
            ][0]
        ):
        fc("function")(fc("code")(
            0,0,0,0,"KABOOM",(),(),(),"","",0,""),{}
            )()
    )()
    """

    # 14 arg code() version - latest versions of python
    v14 = """
    (lambda fc=(
        lambda n: [
            c for c in
                ().__class__.__bases__[0].__subclasses__()
                if c.__name__ == n
            ][0]
        ):
        fc("function")(fc("code")(
            0,0,0,0,0,0,b"KABOOM",(),(),(),"","",0,b""),{}
            )()
    )()
    """

    with pytest.raises(SyntaxError):
        try:
            assert vu.evaluate(v12)
        except TypeError:
            assert vu.evaluate(v14)

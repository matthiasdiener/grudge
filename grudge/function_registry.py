from __future__ import division, with_statement

__copyright__ = """
Copyright (C) 2013 Andreas Kloeckner
Copyright (C) 2019 Matt Wala
"""

__license__ = """
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""


import loopy as lp
import numpy as np

from loopy.version import LOOPY_USE_LANGUAGE_VERSION_2018_1  # noqa
from pytools import RecordWithoutPickling, memoize_in


# {{{ function

class FunctionNotFound(KeyError):
    pass


class Function(RecordWithoutPickling):
    """
    .. attribute:: identifier
    .. attribute:: supports_codegen
    .. automethod:: __call__
    .. automethod:: get_result_dofdesc
    """

    def __init__(self, identifier, **kwargs):
        super(Function, self).__init__(identifier=identifier, **kwargs)

    def __call__(self, queue, *args, **kwargs):
        """Call the function implementation, if available."""
        raise TypeError("function '%s' is not callable" % self.identifier)

    def get_result_dofdesc(self, arg_dds):
        """Return the :class:`grudge.symbolic.primitives.DOFDesc` for the return value
        of the function.

        :arg arg_dds: A list of :class:`grudge.symbolic.primitives.DOFDesc` instances
            for each argument
        """
        raise NotImplementedError


class CElementwiseUnaryFunction(Function):

    supports_codegen = True

    def get_result_dofdesc(self, arg_dds):
        assert len(arg_dds) == 1
        return arg_dds[0]

    def __call__(self, queue, arg):
        func_name = self.identifier

        from numbers import Number
        if (
                isinstance(arg, Number)
                or (isinstance(arg, np.ndarray)
                    and arg.shape == ())):
            func = getattr(np, func_name)
            return func(arg)

        cached_name = "map_call_knl_"

        from pymbolic.primitives import Variable
        i = Variable("i")

        if self.identifier == "fabs":  # FIXME
            # Loopy has a type-adaptive "abs", but no "fabs".
            func_name = "abs"

        cached_name += func_name

        @memoize_in(self, cached_name)
        def knl():
            knl = lp.make_kernel(
                "{[i]: 0<=i<n}",
                [
                    lp.Assignment(Variable("out")[i],
                        Variable(func_name)(Variable("a")[i]))
                ], default_offset=lp.auto)
            return lp.split_iname(knl, "i", 128, outer_tag="g.0", inner_tag="l.0")

        evt, (out,) = knl()(queue, a=arg)
        return out


class CBesselFunction(Function):

    supports_codegen = True

    def get_result_dofdesc(self, arg_dds):
        assert len(arg_dds) == 2
        return arg_dds[1]


class FixedDOFDescExternalFunction(Function):

    supports_codegen = False

    def __init__(self, identifier, implementation, dd):
        super(FixedDOFDescExternalFunction, self).__init__(
                identifier,
                implementation=implementation,
                dd=dd)

    def __call__(self, queue, *args, **kwargs):
        return self.implementation(queue, *args, **kwargs)

    def get_result_dofdesc(self, arg_dds):
        return self.dd

# }}}


# {{{ function registry

class FunctionRegistry(RecordWithoutPickling):
    def __init__(self, id_to_function=None):
        if id_to_function is None:
            id_to_function = {}

        super(FunctionRegistry, self).__init__(
                id_to_function=id_to_function)

    def register(self, function):
        """Return a copy of *self* with *function* registered."""

        if function.identifier in self.id_to_function:
            raise ValueError("function '%s' is already registered"
                    % function.identifier)

        new_id_to_function = self.id_to_function.copy()
        new_id_to_function[function.identifier] = function
        return self.copy(id_to_function=new_id_to_function)

    def __getitem__(self, function_id):
        try:
            return self.id_to_function[function_id]
        except KeyError:
            raise FunctionNotFound(
                    "unknown function: '%s'"
                    % function_id)

    def __contains__(self, function_id):
        return function_id in self.id_to_function

# }}}


def _make_bfr():
    bfr = FunctionRegistry()

    bfr = bfr.register(CElementwiseUnaryFunction("sqrt"))
    bfr = bfr.register(CElementwiseUnaryFunction("exp"))
    bfr = bfr.register(CElementwiseUnaryFunction("fabs"))
    bfr = bfr.register(CElementwiseUnaryFunction("sin"))
    bfr = bfr.register(CElementwiseUnaryFunction("cos"))
    bfr = bfr.register(CBesselFunction("bessel_j"))
    bfr = bfr.register(CBesselFunction("bessel_y"))

    return bfr


base_function_registry = _make_bfr()


def register_external_function(
        function_registry, identifier, implementation, dd):
    return function_registry.register(
            FixedDOFDescExternalFunction(
                identifier, implementation, dd))

# vim: foldmethod=marker

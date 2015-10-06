"""Minimal example of a grudge driver."""

from __future__ import division, print_function

__copyright__ = "Copyright (C) 2015 Andreas Kloeckner"

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


import numpy as np


def main(write_output=True):
    from meshmode.mesh.generation import generate_regular_rect_mesh
    mesh = generate_regular_rect_mesh(a=(-0.5, -0.5), b=(0.5, 0.5))

    from grudge.shortcuts import make_discretization
    discr = make_discretization(mesh, order=4)

    #from grudge.visualization import VtkVisualizer
    #vis = VtkVisualizer(discr, None, "fld")

    source_center = np.array([0.1, 0.22])
    source_width = 0.05
    source_omega = 3

    import grudge.symbolic as sym
    sym_x = sym.nodes(2)
    sym_source_center_dist = sym_x - source_center

    from grudge.models.wave import StrongWaveOperator
    from meshmode.mesh import BTAG_ALL, BTAG_NONE
    op = StrongWaveOperator(-0.1, discr.dimensions,
            source_f=(
                sym.CFunction("sin")(source_omega*sym.ScalarParameter("t"))
                * sym.CFunction("exp")(
                    -np.dot(sym_source_center_dist, sym_source_center_dist)
                    / source_width**2)),
            dirichlet_tag=TAG_NONE,
            neumann_tag=TAG_NONE,
            radiation_tag=TAG_ALL,
            flux_type="upwind")

    from pytools.obj_array import join_fields
    fields = join_fields(discr.volume_zeros(),
            [discr.volume_zeros() for i in range(discr.dimensions)])

    from leap.method.rk import LSRK4TimeStepper
    from leap.vm.codegen import PythonCodeGenerator

    dt_method = LSRK4TimeStepper(component_id="y")
    dt_stepper = PythonCodeGenerator.get_class(dt_method.generate())

    dt = op.estimate_timestep(discr, fields=fields)
    dt_stepper.set_up(t_start=0, dt_start=dt, context={"y": fields})

    final_t = 10
    nsteps = int(final_t/dt)
    print("dt=%g nsteps=%d" % (dt, nsteps))

    step = 0

    for event in dt_stepper.run(t_end=final_t):
        if isinstance(event, dt_stepper.StateComputed):
            assert event.component_id == "y"

            step += 1

            # if step % 10 == 0 and write_output:
            #     print(step, event.t, discr.norm(fields[0]))
            #     visf = vis.make_file("fld-%04d" % step)

            #     vis.add_data(visf,
            #             [("u", fields[0]), ("v", fields[1:]), ],
            #             time=event.t, step=step)
            #     visf.close()

    #vis.close()


if __name__ == "__main__":
    main()

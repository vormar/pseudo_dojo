"""Unit tests for oncvpsp"""
from __future__ import print_function, division

import os
import pytest

from pseudo_dojo.ppcodes.oncvpsp import OncvOuptputParser


def filepath(basename):
    return os.path.join(os.path.dirname(__file__), basename)


def test_oncvoutput_parser():
    """Test the parsing of the output file produced by ONCVPSPS."""

    # TODO: Full-relativistic case not yet supported.
    with pytest.raises(OncvOuptputParser.Error):
        OncvOuptputParser(filepath("08_O_r.out"))

    # Non-relativistic results
    p = OncvOuptputParser(filepath("08_O_nr.out"))
    print(p)
    assert not p.fully_relativistic
    assert p.calc_type == "non-relativistic"

    assert p.atsym == "O"
    assert p.z == "8.00"
    assert p.iexc == "3"
    assert p.lmax == 1

    rhov, rhoc, rhom = p.densities["rhoV"], p.densities["rhoC"], p.densities["rhoM"]
    assert rhov.rmesh[0] == 0.0100642
    assert rhov.rmesh[-1] == 3.9647436
    assert rhoc.values[0] == 53.3293576
    assert all(rhom.values == 0.0)

    # Build the plotter
    plotter = p.make_plotter()

    # Scalar relativistic output
    p = OncvOuptputParser(filepath("08_O_sr.out"))
    assert not p.fully_relativistic
    assert p.calc_type == "scalar-relativistic"
    assert p.lmax == 1

    # Test potentials
    vloc = p.potentials[-1]
    pl0 = {0: -7.4449470, 1: -14.6551019, -1: -9.5661177}

    for l, pot in p.potentials.items():
        assert pot.rmesh[0], pot.rmesh[-1] == (0.0099448, 3.9647436)
        print(l)
        assert pot.values[0] == pl0[l]
        assert all(pot.rmesh == vloc.rmesh)

    # Test wavefunctions
    ae_wfs, ps_wfs = p.radial_wfs.ae, p.radial_wfs.ps

    ae10, ps10 = ae_wfs[(1, 0)], ps_wfs[(1, 0)]
    assert ae10[0] == (0.009945, -0.092997)
    assert ps10[0] == (0.009945,  0.015273)
    assert ae10[-1] == (3.964744, 0.037697)
    assert ps10[-1] == (3.964744, 0.037694)

    ae21, ps21 = ae_wfs[(2, 1)], ps_wfs[(2, 1)]
    assert ae21[0] == (0.009945, 0.001463)
    assert ps21[0] == (0.009945, 0.000396)

    # Test projectors
    prjs = p.projectors
    assert prjs[(1, 0)][0] == (0.009945, 0.015274)
    assert prjs[(2, 0)][0] == (0.009945, -0.009284)
    assert prjs[(1, 0)][-1] == (3.964744, 0.037697)
    assert prjs[(2, 0)][-1] == (3.964744, 0.330625)

    assert prjs[(1, 1)][0] == (0.009945, 0.000395)
    assert prjs[(2, 1)][0] == (0.009945, -0.000282)

    # Test convergence data
    c = p.ene_vs_ecut
    assert c[0].energies[0] == 5.019345
    assert c[0].values[0] == 0.010000
    assert c[0].energies[-1] == 25.317286
    assert c[0].values[-1] == 0.000010
    assert c[1].energies[0] == 19.469226
    assert c[1].values[0] == 0.010000

    # Test log derivatives
    ae0, ps0 = p.atan_logders.ae[0], p.atan_logders.ps[0]
    assert ae0.energies[0], ae0.values[0] == (2.000000, 0.706765)
    assert ps0.energies[0], ps0.values[0] == (2.000000, 0.703758)
    assert ae0.energies[-1], ae0.energies[-1] == (-2.000000, 3.906687)
    assert ps0.energies[-1], ps0.energies[-1] == (-2.000000, 3.906357)

    ae1, ps1 = p.atan_logders.ae[1], p.atan_logders.ps[1]
    assert ae1.energies[0], ae1.values[0]  == (2.000000, -2.523018)
    assert ps1.values[0] == -2.521334


# -*- coding: utf-8 -*-
'''
EXPOsan: Exposition of sanitation and resource recovery systems

This module is developed by:
    Joy Zhang <joycheung1994@gmail.com>

This module is under the University of Illinois/NCSA Open Source License.
Please refer to https://github.com/QSD-Group/EXPOsan/blob/main/LICENSE.txt
for license details.
'''

__all__ = ('test_bsm1',)

def test_bsm1():
    from numpy.testing import assert_allclose as ac
    from numpy import arange
    from exposan import bsm1

    bsm1.load()
    sys = bsm1.sys
    sys.simulate(t_span=(0,50), method='BDF', t_eval=arange(0, 51, 1))
    assert sys.outs[0].isempty() == False
    ac(float(sys.outs[0].iconc['S_S']), 0.895, rtol=1e-2)
    ac(float(sys.outs[1].iconc['X_BH']), 4994.3, rtol=1e-2)
    ac(sys.outs[0].COD, 47.5, rtol=1e-2)
    ac(sys.outs[1].get_TSS(), 6377.9, rtol=1e-2)


if __name__ == '__main__':
    test_bsm1()
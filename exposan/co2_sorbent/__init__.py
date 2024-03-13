#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
EXPOsan: Exposition of sanitation and resource recovery systems

This module is developed by:
    
    Jianan Feng <jiananf2@gmail.com>
    
This module is under the University of Illinois/NCSA Open Source License.
Please refer to https://github.com/QSD-Group/EXPOsan/blob/main/LICENSE.txt
for license details.
'''

import os, pandas as pd, qsdsan as qs
from qsdsan.utils import auom
from exposan.utils import _init_modules
from datetime import date

sorbent_path = os.path.dirname(__file__)
module = os.path.split(sorbent_path)[-1]
data_path, results_path = _init_modules(module, include_data_path=True)

# %%

# =============================================================================
# Load components and systems
# =============================================================================

from . import _components
from ._components import *
_components_loaded = False
def _load_components(reload=False):
    global components, _components_loaded
    if not _components_loaded or reload:
        components = create_components()
        qs.set_thermo(components)
        _components_loaded = True

# from . import _tea
# from ._tea import *

from . import systems
from .systems import *

# _system_loaded = False
# def load(configuration='baseline'):
#     global sys, tea, lca, flowsheet, _system_loaded
#     sys = create_system(configuration)
#     tea = sys.TEA
#     lca = sys.LCA
#     flowsheet = sys.flowsheet
#     _system_loaded = True
#     dct = globals()
#     dct.update(sys.flowsheet.to_dict())

# def __getattr__(name):
#     if not _components_loaded or not _system_loaded:
#         raise AttributeError(
#             f'Module {__name__} does not have the attribute "{name}" '
#             'and the module has not been loaded, '
#             f'loading the module with `{__name__}.load()` may solve the issue.')
        
# from . import models
# from .models import *

# def simulate_and_save(model,
#                       resample=True, samples_kwargs={'N':1000, 'rule':'L', 'seed':3221},
#                       include_spearman=True, spearman_kwargs={'nan_policy': 'omit'},
#                       export_results=True, path='',notes=''):
#     if resample:
#         kwargs = {'N':1000, 'rule':'L', 'seed':None}
#         kwargs.update(samples_kwargs)
#         samples = model.sample(**kwargs)
#         model.load_samples(samples)
#     model.evaluate()
#     idx = len(model.parameters)
#     parameters = model.table.iloc[:, :idx]
#     results = model.table.iloc[:, idx:]
#     percentiles = results.quantile([0, 0.05, 0.25, 0.5, 0.75, 0.95, 1])
#     if include_spearman:
#         kwargs = {'nan_policy': 'omit'}
#         kwargs.update(spearman_kwargs)
#         r_df, p_df = qs.stats.get_correlations(model, kind='Spearman', **kwargs)

#     if export_results:
#         ID = model.system.flowsheet.ID
#         N = model.table.shape[0]
#         path = path or os.path.join(results_path, f'{date.today()}_{ID}_{N}_{notes}.xlsx')
#         with pd.ExcelWriter(path) as writer:
#             parameters.to_excel(writer, sheet_name='Parameters')
#             results.to_excel(writer, sheet_name='Results')
#             percentiles.to_excel(writer, sheet_name='Percentiles')
#             if include_spearman:
#                 r_df.to_excel(writer, sheet_name='Spearman_r')
#                 p_df.to_excel(writer, sheet_name='Spearman_p')

__all__ = (
    'sorbent_path',
    'data_path',
    'results_path',
    'simulate_and_save',
    *_components.__all__,
    # *_tea.__all__,
    *systems.__all__,
    # *models.__all__,
)
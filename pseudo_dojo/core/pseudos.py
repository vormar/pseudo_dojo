# coding: utf-8
"""Public API to access the pseudopotential tables."""
from __future__ import division, print_function, unicode_literals

import os
import json
import numpy as np

from monty.collections import AttrDict 
from monty.string import list_strings
from pymatgen.core.periodic_table import PeriodicTable
from pymatgen.util.plotting_utils import add_fig_kwargs #, get_ax_fig_plt
from pymatgen.io.abinitio.pseudos import PseudoTable 


class DojoInfo(AttrDict):
    """Dictionary with metadata associated to the table."""

    # See http://validictory.readthedocs.org/en/latest/usage.html#schema-options
    JSON_SCHEMA = {
        "type": "object",
        "properties": {
            "pseudo_type": {"type": "string", "enum": ["norm-conserving", "PAW"]},
            "xc_type": {"type": "string", "enum": ["GGA-PBE",]},
            "authors": {"type": "array"},
            "generation_date": {"type": "string", "format": "date"},
            "description": {"type": "string"},
            #"tags": {"type": "array", "items": {"type": "string", "enum": ["accuracy", "efficiency"]}},
            "reference": {"type": "string"},
            "dojo_dir": {"type": "string"},
            #non-relativistic, scalar-relativistic or relativistic
        },
    }

    def validate_json_schema(self):
        """Validate DojoInfo with validictory."""
        import validictory
        validictory.validate(self, self.JSON_SCHEMA)

    @property
    def isnc(self):
        """True if norm-conserving pseudopotential."""
        return self.pseudo_type == "norm-conserving"

    @property
    def ispaw(self):
        """True if PAW pseudopotential."""
        return self.pseudo_type == "PAW"


class DojoTable(PseudoTable):
    """
    A pseudopotential table provided by pseudo_dojo.
    We subclass `PseudoTable` so that we can easily add 
    extra properties or methods, if needed.
    """

    @classmethod
    def from_dojodir(cls, top, exclude_basenames=None):
        """
        Initialize the table of pseudos for one of the top level directories
        located in the pseudo_dojo.pseudos directory.

        Args:
            exclude_basenames: Optional string or list of strings with the 
                pseudo basenames to be excluded.

        .. warning::
            
            The table may contain multiple pseudos for a given chemical element.
            Don't use this method unless you need this feature and you know what 
            you are doing.
        """
        # Read metadata from the __init__.py file
        import imp
        module_name = os.path.join(top, "__init__.py")
        meta = imp.load_source(module_name, os.path.join(top, "__init__.py") )

        # Gather all pseudos starting from the current working directory 
        all_symbols = set(element.symbol for element in PeriodicTable().all_elements)
        dirs = [os.path.join(top, d) for d in os.listdir(top) if d in all_symbols]

        exclude = set(list_strings(exclude_basenames)) if exclude_basenames is not None else set()

        paths = []
        for dir in dirs:
            paths.extend(os.path.join(dir, f) for f in os.listdir(dir) 
                         if f.endswith(meta.pseudo_ext)
                         and f not in exclude #!= "Sr-sp.psp8"
                         )

        new = cls(paths).sort_by_z()
        return new

    @classmethod
    def from_djson(cls, djson_path):
        """
        Initialize the table of pseudos for one of **official"" djson files 
        located in the subdirectories on pseudo_dojo.pseudos.

        .. important::

            The table contains one pseudo per element and can be used for production calculations

        djson_path contains the dictionary:

        {
        "dojo_info": {
              "pseudo_type": "norm-conserving",
              "xc_type": "GGA-PBE",
              "authors": ["M. Giantomassi", "M. J van Setten"],
              "generation_date": "2015-07-20",
              "description": "String",
              "tags": ["accuracy", "tag2"],
              "reference": "paper",
              "dojo_dir": "ONCVPSP-PBE",
        },
        "pseudos_metadata": {
            "Si": {
                "basename": "Si-dloc.psp8", 
                "Z_val": 4.0, 
                "l_max": 2, 
                "md5": "ececcf5b26f34676694b630d6bc809ff"
            }, 
            "O": {
                "basename": "O-dmax.psp8", 
                "Z_val": 6.0, 
                "l_max": 2, 
                "md5": "f7d0f3573362d89c81c41fc6b7b3e6ab"
            }
        }
        }
        """
        with open(djson_path, "rt") as fh:
            d = json.loads(fh.read())

        dojo_info = DojoInfo(**d["dojo_info"])
        dojo_info.validate_json_schema()

        meta = d["pseudos_metadata"]

        top = os.path.dirname(djson_path)

        paths, md5dict = [], {}
        for esymb, m in meta.items():
            paths.append(os.path.join(top, esymb, m["basename"]))
            md5dict[m["basename"]] = m["md5"]

        new = cls(paths).sort_by_z()
        new.set_dojo_info(dojo_info)

        errors = new.dojo_check_errors(md5dict)
        if errors:
            raise ValueError("\n".join(errors))

        return new

    @property
    def dojo_info(self):
        try:
            return self._dojo_info
        except AttributeError:
            return {}

    #@dojo_info.setter
    def set_dojo_info(self, dojo_info):
        self._dojo_info = dojo_info

    #def show_dojo_info(self):
    #    print(self.dojo_info)

    # TODO: Move to require_hints == True
    def dojo_check_errors(self, md5dict, require_hints=False):
        """
        This function tests whether the table fulfill the requirements 
        imposed by the PseudoDojo. More specifically:

            #. One pseudo per element.

            #. All pseudos should have a valid dojo report with hints

            #. The md5 value computed from the pseudo potential file must agree
               with the one found in the djson file.
        
        Args:
            md5dict: dict basename --> md5 hash value
        """
        errors = []
        eapp = errors.append

        unique_symbols = set([p.symbol for p in self])
        if len(unique_symbols) != len(self):
            eapp("Found multiple pseudos for a given element.")

        for p in self:
            if not p.has_dojo_report:
                eapp("%s does not have the DOJO_REPORT section" % repr(p))
                continue

            elist = p.dojo_report.check_errors()
            if elist:
                errors.extend(elist)

            if require_hints and not p.dojo_report.has_hints:
                eapp("%s does not have hints" % repr(p))

            if p.md5 != md5dict[p.basename]:
                app("p.mdf5 != mdf5dict[p.basename]\n%s, %s" % (p.md5, md5dict[p.basename]))

        return errors

    def get_dfgbrv_dataframe(self):
        """
        Build and return a pandas :class:`DataFrame` in the form.

            basename     deltafactor  df_prime  gbrv_bcc  gbrv_fcc  symbol   md5 
            H-high.psp8  0.074830     1.258340  0.028904  0.024726  H        5863396c90149cbe12af496141bde0d0 
            ...

        where `gbrv_bcc` and `gbrv_fcc` are the relative errors (in percentage) wrt the AE calculations.
        """
        _TRIALS2KEY = {
            "deltafactor": "dfact_meV",
            "gbrv_bcc": "a0_rel_err",
            "gbrv_fcc": "a0_rel_err",
        }

        rows = []
        for p in self:
            # Extract the dojo_report
            report = p.dojo_report

            row = dict(basename=p.basename, symbol=p.symbol, md5=p.md5)

            for trial, key in _TRIALS2KEY.items():
                # Get results as function of ecut
                try:
                    data = report[trial]
                except KeyError:
                    print("%s does not have %s" % (p.basename, trial))
                    continue

                # Extract the value with highest ecut.
                high_ecut = list(data.keys())[-1]
                row.update({trial: data[high_ecut][key]})
                if trial == "deltafactor":
                    row.update(dict(df_prime=data[high_ecut]["dfactprime_meV"]))

            rows.append(row)

        from pandas import DataFrame
        return DataFrame(rows)

    @add_fig_kwargs
    def plot_dfgbrv_dist(self, **kwargs):
        """
        Plot four distribution plots for the deltafactor, deltafactor prime and the 
        relative errors for the GBRV fcc, bcc structures.

        Return: `matplotlib` figure.
        """
        import matplotlib.pyplot as plt
        fig, ax_list = plt.subplots(nrows=2, ncols=2, squeeze=True)
        ax_list = ax_list.ravel()

        frame = self.get_dfgbrv_dataframe()

        import seaborn as sns
        for ax, col in zip(ax_list.ravel(), ["deltafactor", "gbrv_fcc", "df_prime", "gbrv_bcc"]):
            values = frame[col].dropna() 
            sns.distplot(values, ax=ax, rug=True, hist=True, kde=False, label=col, bins=kwargs.pop("bins", 50))

            # Add text with Mean or (MARE/RMSRE)
            text = []; app = text.append
            if col in ("deltafactor", "df_prime"):
                app("Mean = %.2f" % values.mean())
            else:
                app("MARE = %.2f" % values.abs().mean())
                app("RMSRE = %.2f" % np.sqrt((values**2).mean()))

            ax.text(0.8, 0.8, "\n".join(text), transform=ax.transAxes)

        return fig

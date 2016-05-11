from . import StationDingo
from dingo.core.network import TransformerDingo
from itertools import compress

class MVStationDingo(StationDingo):
    """
    Defines a MV station in DINGO
    -----------------------------
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return 'mvstation_' + str(self.id_db)

    def choose_transformers(self, transformers, **kwargs):
        """Chooses appropriate transformers for the MV sub-station

        Choice bases on voltage level (depends on load density), apparent power
        and general planning principles for MV distribution grids.

        Parameters
        ----------
        transformers : dict
            Contains technical information of p hv/mv transformers
        **kwargs : dict
            Should contain a value behind the key 'peak_load'

        Notes
        -----
        Potential hv-mv-transformers are chosen according to [2]_.
        Parametrization of transformers bases on [1]_.

        References
        ----------
        .. [1] Deutsche Energie-Agentur GmbH (dena), "dena-Verteilnetzstudie.
            Ausbau- und Innovationsbedarf der Stromverteilnetze in Deutschland
            bis 2030.", 2012
        .. [2] X. Tao, "Automatisierte Grundsatzplanung von
            Mittelspannungsnetzen", Dissertation, 2006

        """

        # step 1: identify possible transformers by voltage level
        # TODO: derive voltage level by load density of mv_region
        voltage_level = 10 # in kV

        apparent_power = kwargs.get('peak_load', None) # kW
        possible_tranformers = []   # keys of above dict

        # put all keys of suitable transformers (based on voltage) to list
        for trans in transformers:
            if voltage_level == transformers[trans]['voltage_level']:
                possible_tranformers.append(trans)

        # step 2: determine number and size of required transformers
        residual_apparent_power = apparent_power

        apparent_power_list = [transformers[x]['apparent_power']
                               for x in possible_tranformers]

        while residual_apparent_power > 0:
            # TODO: move constant value 0.6 (load factor) to config file
            if residual_apparent_power > 0.6 * max(possible_tranformers):
                selected_app_power = max(possible_tranformers)
            else:
                selected_app_power = min(list(compress(possible_tranformers,
                    [residual_apparent_power<=k
                     for k in possible_tranformers])))

            # add tranformer on determined size with according parameters
            self.add_transformer(TransformerDingo(**{'v_level': voltage_level,
                's_max_longterm': selected_app_power}))
            residual_apparent_power -= selected_app_power

        # add redundant transformer of the size of the largest tranformer
        s_max_max = max((o.s_max_a for o in self._transformers))
        int_kwargs = {'v_level': voltage_level,
                      's_max_longterm': s_max_max}

        self.add_transformer(TransformerDingo(**int_kwargs))


class LVStationDingo(StationDingo):
    """
    Defines a LV station in DINGO
    -----------------------------
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return 'lvstation_' + str(self.id_db)
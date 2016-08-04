from . import CableDistributorDingo


class MVCableDistributorDingo(CableDistributorDingo):
    """ Cable distributor (connection point) """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.grid = kwargs.get('grid', None)
        self.lv_load_area_group = kwargs.get('lv_load_area_group', None)

        # get id from count of cable distributors in associated MV grid
        self.id_db = self.grid.cable_distributors_count() + 1

    def __repr__(self):
        return 'mv_cable_dist_' + str(self.id_db)


class LVCableDistributorDingo(CableDistributorDingo):
    """LV Cable distributor (connection point) """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.string_id = kwargs.get('string_id', None)
        self.branch_no = kwargs.get('branch_no', None)
        self.load_no = kwargs.get('load_no', None)

    def __repr__(self):
        return ('lv_cable_dist_' + str(self.id_db) + '_' + str(self.string_id) + '-'
            + str(self.branch_no) + '_' + str(self.load_no))

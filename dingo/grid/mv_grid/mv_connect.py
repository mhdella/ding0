
from dingo.core.network.stations import *
from dingo.core.network import BranchDingo, CableDistributorDingo
#from dingo.core.structure.regions import LVRegionGroupDingo
from dingo.tools.geo import calc_geo_dist_vincenty
from dingo.tools import config as cfg_dingo

from shapely.geometry import LineString, Point, MultiPoint
from shapely.ops import transform
import pyproj
from functools import partial

import time


def mv_connect(graph, dingo_object, debug=False):
    """ Connects DINGO objects to MV grid, e.g. load areas of type `satellite`, DER etc.

    Method:
        1. Find nearest line for every satellite using shapely distance:
            Transform  to equidistant CRS
        2. ...

    Args:
        graph: NetworkX graph object with nodes
        dingo_object: component (instance(!) of Dingo class) to be connected
            Valid objects:  LVStationDingo (small load areas that are not incorporated in cvrp MV routing)
                            MVDEA (MV renewable energy plants) (not existent yet)
            CAUTION: `dingo_object` is not connected but it specifies the types of objects that are to be connected,
                     e.g. if LVStationDingo() is passed, all objects of this type within `graph` are connected.
        debug: If True, information is printed during process

    Returns:
        graph: NetworkX graph object with nodes and newly created branches
    """
    # TODO: Complete docstring

    start = time.time()

    # conn_dist_weight: The satellites can be connected to line (new terminal is created) or to one station where the
    # line ends, depending on the distance from satellite to the objects. This threshold is a length weighting to prefer
    # stations instead of direct line connection to respect grid planning principles.
    # Example: The distance from satellite to line is 1km, to station1 1.2km, to station2 2km.
    # With conn_dist_threshold=0.75, the 'virtual' distance to station1 would be 1.2km * 0.75 = 0.9km, so this conn.
    # point would be preferred.
    conn_dist_weight = cfg_dingo.get('mv_connect', 'load_area_sat_conn_dist_weight')

    # conn_dist_ring_mod: Allow re-routing of ring main route if node is closer than this threshold (in m) to ring.
    conn_dist_ring_mod = cfg_dingo.get('mv_connect', 'load_area_sat_conn_dist_ring_mod')

    # check if dingo_object is valid object
    # TODO: Add RES to isinstance check
    if isinstance(dingo_object, (LVStationDingo, LVStationDingo)):

        # startx = time.time()
        # nodes_pos = {}
        # for node in graph.nodes():
        #     if isinstance(node, LVStationDingo):
        #         if node.grid.region.is_satellite:
        #             nodes_pos[str(node)] = (node.geo_data.x, node.geo_data.y)
        # matrix = calc_geo_dist_vincenty(nodes_pos)
        # print('Elapsed time (vincenty): {}'.format(time.time() - startx))



        # WGS84 (conformal) to ETRS (equidistant) projection
        proj1 = partial(
                pyproj.transform,
                pyproj.Proj(init='epsg:4326'),  # source coordinate system
                pyproj.Proj(init='epsg:3035'))  # destination coordinate system

        # ETRS (equidistant) to WGS84 (conformal) projection
        proj2 = partial(
                pyproj.transform,
                pyproj.Proj(init='epsg:3035'),  # source coordinate system
                pyproj.Proj(init='epsg:4326'))  # destination coordinate system

        # check all nodes
        for node in graph.nodes():
            if isinstance(dingo_object, LVStationDingo):

                # station is LV station
                if isinstance(node, LVStationDingo):

                    # satellites only
                    if node.grid.region.is_satellite:

                        satellite_shp = Point(node.geo_data.x, node.geo_data.y)
                        satellite_shp = transform(proj1, satellite_shp)

                        dist_min = 10**6  # initial distance value in m

                        # === FIND ===
                        # calc distance between node and grid's lines -> find nearest line
                        # TODO: performance: don't calc distance for all edges, only surrounding ones (but how?)
                        for branch in node.grid.region.mv_region.mv_grid.graph_edges():
                            stations = branch['adj_nodes']

                            # shapely objects for 2 stations and line between them
                            station1_shp = Point((stations[0].geo_data.x, stations[0].geo_data.y))
                            station2_shp = Point((stations[1].geo_data.x, stations[1].geo_data.y))
                            line_shp = LineString([station1_shp, station2_shp])

                            # transform to equidistant CRS
                            line_shp = transform(proj1, line_shp)
                            station1_shp = transform(proj1, station1_shp)
                            station2_shp = transform(proj1, station2_shp)

                            # create dict with DINGO objects (line & 2 adjacent stations), shapely objects and distances
                            conn_objects = {'s1': {'obj': stations[0],
                                                   'shp': station1_shp,
                                                   'dist': satellite_shp.distance(station1_shp) * conn_dist_weight},
                                            's2': {'obj': stations[1],
                                                   'shp': station2_shp,
                                                   'dist': satellite_shp.distance(station2_shp) * conn_dist_weight},
                                            'b': {'obj': branch,
                                                  'shp': line_shp,
                                                  'dist': satellite_shp.distance(line_shp)}}

                            # find nearest connection point on given triple dict
                            conn_objects_min = min(conn_objects.values(), key=lambda v: v['dist'])

                            # current obj closer than previous closest?
                            if conn_objects_min['dist'] < dist_min:
                                dist_min = conn_objects_min['dist']
                                dist_min_obj = conn_objects_min

                        # === CONNECT ===
                        # MV line is nearest connection point
                        if isinstance(dist_min_obj['shp'], LineString):

                            # find nearest point on MV line
                            conn_point_shp = dist_min_obj['shp'].interpolate(dist_min_obj['shp'].project(satellite_shp))
                            conn_point_shp = transform(proj2, conn_point_shp)

                            # Node is close to line
                            # -> insert node into route (change existing route)
                            if dist_min_obj['dist'] < conn_dist_ring_mod:

                                # split old ring main route into 2 segments (delete old branch and create 2 new ones
                                # along node)
                                graph.remove_edge(dist_min_obj['obj']['adj_nodes'][0], dist_min_obj['obj']['adj_nodes'][1])
                                graph.add_edge(dist_min_obj['obj']['adj_nodes'][0], node, branch=BranchDingo())
                                graph.add_edge(dist_min_obj['obj']['adj_nodes'][1], node, branch=BranchDingo())

                                if debug:
                                    print('Ring main Route modified to include node', node)

                            # Node is too far away from route
                            # => keep main route and create new line from node to route
                            else:

                                # create cable distributor and add it to grid
                                cable_dist = CableDistributorDingo(geo_data=conn_point_shp)
                                node.grid.region.mv_region.mv_grid.add_cable_distributor(cable_dist)

                                # split old branch into 2 segments (delete old branch and create 2 new ones along cable_dist)
                                graph.remove_edge(dist_min_obj['obj']['adj_nodes'][0], dist_min_obj['obj']['adj_nodes'][1])
                                graph.add_edge(dist_min_obj['obj']['adj_nodes'][0], cable_dist, branch=BranchDingo())
                                graph.add_edge(dist_min_obj['obj']['adj_nodes'][1], cable_dist, branch=BranchDingo())

                                # add new branch for satellite (station to cable distributor)
                                # TODO: hier nur T-Muffe, Einschleifung muss rein
                                graph.add_edge(node, cable_dist, branch=BranchDingo())

                                # debug info
                                if debug:
                                    print('Nearest connection point for object', node, 'is branch',
                                          dist_min_obj['obj']['adj_nodes'], '(distance=', dist_min_obj['dist'], 'm)')

                        # MV/LV station ist nearest connection point
                        else:
                            # add new branch for satellite (station to station)
                            graph.add_edge(node, dist_min_obj['obj'], branch=BranchDingo())

                            # debug info
                            if debug:
                                print('Nearest connection point for object', node, 'is station',
                                      dist_min_obj['obj'], '(distance=', dist_min_obj['dist'], 'm)')

                        # ==== FIRST DRAFT FOR GROUP HANDLING ===
                        # else:
                        #     # check if target station is within a satellite string yet (member of a LV region group)
                        #     lv_region_group = dist_min_obj['obj'].grid.region.lv_region_group
                        #
                        #     # if not:
                        #     if lv_region_group is None:
                        #
                        #         # create new LV region group for current node
                        #         lv_region_group = LVRegionGroupDingo()
                        #         lv_region_group.add_lv_region(node.grid.region)
                        #         node.grid.region.lv_region_group = lv_region_group
                        #
                        #         # add new branch for satellite (station to station)
                        #         graph.add_edge(node, dist_min_obj['obj'], branch=BranchDingo())
                        #
                        #         # debug info
                        #         if debug:
                        #             print('Nearest connection point for object', node, 'is station',
                        #                   dist_min_obj['obj'], '(distance=', dist_min_obj['dist'], 'm)')
                        #
                        #     # target station is member of a LV region group
                        #     else:
                        #         if lv_region_group.can_add_lv_region(node.grid.region):
                        #             lv_region_group.add_lv_region(node.grid.region)
                        #             node.grid.region.lv_region_group = lv_region_group
                        #         else:
                        #             print('wtf')

                        # TODO: Parametrize new lines!

        if debug:
            print('Elapsed time (mv_connect): {}'.format(time.time() - start))

        return graph

    else:
        print('argument `dingo_object` has invalid value, see method for valid inputs.')
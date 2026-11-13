class TD_and_DC:
    def __init__(self, b_id, b_name, f_id, f_name, f_poly, st_data, p_data, ft_data, fd_data):
        self.b_id = b_id
        self.b_name = b_name
        self.f_id = f_id
        self.f_name = f_name
        self.f_poly = f_poly
        self.st_data = st_data
        self.p_data = p_data
        self.ft_data = ft_data
        self.fd_data = fd_data

    # ----------------------------------------------------------
    # Staircase fallback: combine the extremes and pick the first distance >= 4.
    # ----------------------------------------------------------
    def apply_dc_rule_firedoors(self, min_list, max_list, DC_DISTANCE=4.0):
        min_max_dis = []
        if min_list:
            min_max_dis.extend(min_list)
        if max_list:
            min_max_dis.extend(max_list)

        if not min_max_dis:
            return None

        for dis in sorted(min_max_dis):
            if dis >= DC_DISTANCE:
                return dis

        return None

    # ----------------------------------------------------------
    # Door outlines establish stair/tower contact; label points are used for measurement.
    # ----------------------------------------------------------
    def get_valid_firedoors_for_stair(self, stair_polygon):
        return self._get_firedoors((stair_polygon,), include_detached=False)

    def _get_firedoors(self, stair_polygons, *, include_detached):
        FD_List_D = []
        # collect only SAME-FLOOR fire towers
        same_floor_towers = []
        for ft_values in self.ft_data.values():
            ft_poly = ft_values[-1]
            if self.f_poly.contains(ft_poly) or round(self.f_poly.distance(ft_poly), 1) == 0.0:
                same_floor_towers.append(ft_poly)

        for fd_values in self.fd_data.values():
            fd_label = fd_values[0].lower().replace(" ", "")
            if not ("firedoor" in fd_label or "exitdoor" in fd_label or "fireeixtdoor" in fd_label):
                continue

            door_polygon, label_point = fd_values[1:3]
            if ((include_detached and self.f_poly.covers(label_point))
                    or any(round(stair.distance(door_polygon), 1) == 0.0 for stair in stair_polygons)
                    or any(round(tower.distance(door_polygon), 1) == 0.0 for tower in same_floor_towers)):
                FD_List_D.append([label_point, door_polygon, fd_label])

        return FD_List_D

    # ----------------------------------------------------------
    # stair_touch_passage (DISTANCE FOR EVERY PASSAGE)
    # ----------------------------------------------------------
    def stair_touch_passage(self, stair_polygon, stair_id, stair_label, fd_points):
        passage_map = {}
        for passage_id, passage_values in self.p_data.items():
            passage_polygon = passage_values[1]
            if not self.f_poly.contains(passage_polygon):
                continue
            center_line_pts = [xy[0:2] for xy in passage_values[2].get_points()]
            if not center_line_pts:
                continue
            center_points = [Point(xy) for xy in dict.fromkeys(map(tuple, center_line_pts))]
            if not fd_points:
                continue
            if fd_points[0][0] is None:
                distances = [stair_polygon.distance(vertex) for vertex in center_points]
                final_dc = self.apply_dc_rule_firedoors([min(distances)], [max(distances)])
            else:
                door_distances = []
                for door_point, _, _ in fd_points:
                    # Try the second closest vertex if the first does not clear 4 m.
                    nearest_two = sorted(door_point.distance(vertex) for vertex in center_points)[:2]
                    for distance in nearest_two:
                        if distance > 4.0:
                            door_distances.append(distance)
                            break
                final_dc = min(door_distances, default=None)

            if final_dc is None:
                continue

            # DO NOT change dict key names
            passage_map[passage_id] = {
                "BLDG_ID": self.b_id,
                "BLDG_LABEL": self.b_name,
                "FLOOR_ID": self.f_id,
                "FLOOR_LABEL": self.f_name,
                "STAIR_ID": stair_id,
                "STAIR_LABEL": stair_label,
                "PASSAGE_ID": passage_id,
                "PASSAGE_LABEL": passage_values[0],
                "DC_DISTANCE": str(round(final_dc,2))
            }

        return list(passage_map.values())

    # ----------------------------------------------------------
    # MAIN FUNCTION
    # ----------------------------------------------------------
    def get_dc(self):

        if "basement" in self.f_name.lower():
            return
        floor_stairs = {key: stair for key, stair in self.st_data.items()
                        if self.f_poly.contains(stair[1])}
        if not floor_stairs:
            return []
        fd_points = self._get_firedoors([stair[1] for stair in floor_stairs.values()], include_detached=True)
        if fd_points:
            rows = self.stair_touch_passage(None, None, None, fd_points)
        else:
            td_and_dc_map = {}
            for stair_id, stair_values in floor_stairs.items():
                stair_data = self.stair_touch_passage(stair_values[1], stair_id, stair_values[0],
                                                      [(None, None, "stair")])
                for res in stair_data:
                    pid = res["PASSAGE_ID"]
                    if (
                        pid not in td_and_dc_map or
                        float(res["DC_DISTANCE"]) < float(td_and_dc_map[pid]["DC_DISTANCE"])
                    ):
                        td_and_dc_map[pid] = res

            rows = list(td_and_dc_map.values())

        for row in rows:
            passage = self.p_data[row["PASSAGE_ID"]][1]
            nearest_id = min(floor_stairs, key=lambda key: passage.distance(floor_stairs[key][1]))
            row["STAIR_ID"] = nearest_id
            row["STAIR_LABEL"] = floor_stairs[nearest_id][0]
        return rows
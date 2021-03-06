"""
ArcGIS Python Toolbox with geoprocessing tools for KIMU project.

Primary tool converts the file geodatabase from the Park Observer
survey archive for the Kittlitz's Murrelet (KIMU) survey in Glacier
Bay done by the South East Alaska I&M Network into a CSV in a
specific protocol required by Survey Protocol.

This tool is specific to The output protocol format specified in
the `default_config` portion at the start of the code, as well as
the Park Observer Survey Protocol file (scattered through out the
code). This includes the mis-spelling of KitlitzCount (See
https://github.com/AKROGIS/Park-Observer-Website/blob/master/protocols/sean_kimu.obsprot)

Written for Python 2.7; should work with Python 3.x.
Requires the Esri ArcGIS arcpy module.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import calendar
import csv
import datetime
import os
import sys

import arcpy


default_config = {
    "gdb": "",
    "csv": "",
    "protocol": "KM-2019.1",
    "header": "TRANSECT_ID,DATE_LOCAL,TIME_LOCAL,VESSEL,RECORDER,OBSERVER_1,OBSERVER_2,"
    + "BEAUFORT,WEATHER_CODE,VISIBILITY,LATITUDE_WGS84,LONGITUDE_WGS84,"
    + "UTM8_EASTING,UTM8_NORTHING,SPEED,BEARING,ANGLE,DISTANCE,BEHAVIOR,"
    + "GROUP_SIZE,SPECIES,ON_TRANSECT,PROTOCOL_ID,GPS_STATUS,SATELLITES,"
    + "HDOP,TRACK_LENGTH,COMMENTS,DATA_QUALITY,DATA_QUALITY_COMMENT,OBSERVED_BY",
}


class Toolbox(object):
    """Define the toolbox (the name of the toolbox is the name of the .pyt file)."""

    # This class is specified by esri's Toolbox framework
    # pylint: disable=useless-object-inheritance,too-few-public-methods

    def __init__(self):
        self.label = "KIMU Toolbox"
        self.alias = "KIMU"
        self.description = "A Toolbox for processing KIMU data for SEAN."
        self.tools = [ExportCSV]


# noinspection PyPep8Naming,PyMethodMayBeStatic,PyUnusedLocal
class ExportCSV(object):
    """GP Tool to export the protocol CSV."""

    # A GP Tool class structure is specified by esri's Toolbox framework.
    # pylint: disable=useless-object-inheritance,invalid-name,no-self-use, unused-argument

    def __init__(self):
        self.label = "FGDB to CSV"
        self.description = (
            "Creates CSV file having mm/dd/yyyy dates compliant with KIMU Protocol version {} "
            "from a Park Observer Survey FGDB.".format(default_config["protocol"])
        )

    def getParameterInfo(self):
        """Set up the input form with the parameter list and options."""
        fgdb = arcpy.Parameter(
            name="fgdb",
            displayName="Survey FGDB",
            direction="Input",
            datatype="DEWorkspace",
            parameterType="Required",
        )
        fgdb.filter.list = ["poz"]
        csv_folder = arcpy.Parameter(
            name="csv_folder",
            displayName="Output Folder",
            direction="Input",
            datatype="DEFolder",
            parameterType="Required",
        )
        csv_file = arcpy.Parameter(
            name="csv_file",
            displayName="CSV Filename",
            direction="Input",
            datatype="String",
            parameterType="Required",
        )

        parameters = [fgdb, csv_folder, csv_file]
        return parameters

    def updateParameters(self, parameters):
        """Update the parameter values after a user's parameter change."""
        # Nothing to do.

    def updateMessages(self, parameters):
        """Update Error,Warning, and Info messages after a user's parameter change."""
        # Nothing to do.

    def execute(self, parameters, messages):
        """The user has press 'GO', so execute the task."""
        config = dict(default_config)
        config["gdb"] = parameters[0].valueAsText
        config["csv"] = os.path.join(
            parameters[1].valueAsText, parameters[2].valueAsText
        )
        create_csv(config)


def utc_to_local(utc_dt):
    """
    Converts a datetime from UTC to a Local;
    Stolen from http://stackoverflow.com/a/13287083/542911

    :param utc_dt: a python datetime in UTC
    :return: a python datetime in the computers local timezone
    """

    # get integer timestamp to avoid precision lost
    timestamp = calendar.timegm(utc_dt.timetuple())
    local_dt = datetime.datetime.fromtimestamp(timestamp)
    assert utc_dt.resolution >= datetime.timedelta(microseconds=1)
    return local_dt.replace(microsecond=utc_dt.microsecond)


def get_gps_points(config):
    """
    Queries an ArcGIS database and returns information on the track logs in it.

    :param config: a dictionary of configuration options
    :return: a dictionary with an integer key (GPSPoint_ID), and a dictionary for a value.
    The dictionary contains exactly the string keys:
      'DATE_LOCAL': value is a string in the format MM/DD/YYYY representing a date
      'TIME_LOCAL': value is a string in the format HH:MM:SS representing a time
      'LATITUDE_WGS84','LONGITUDE_WGS84': values are doubles
      'UTM8_EASTING','UTM8_NORTHING': values are optional doubles
      'SPEED','BEARING': values are optional doubles
      'GPS_STATUS','SATELLITES': values are optional integers
      'HDOP': value is an optional double
      'TRACKLOG_ID': value is an integer
    """

    results = {}
    features = os.path.join(config["gdb"], "GpsPoints")
    spatial_ref = arcpy.SpatialReference(3715)  # NAD83(NSRS2007) / UTM zone 8N
    fields = [
        "OID@",
        "Timestamp",
        "Latitude",
        "Longitude",
        "Shape@X",
        "Shape@Y",
        "Speed_mps",
        "Course",
        "TrackLog_ID",
    ]
    with arcpy.da.SearchCursor(features, fields, None, spatial_ref) as cursor:
        for row in cursor:
            datetime_utc = datetime.datetime.strptime(row[1], "%Y-%m-%dT%H:%M:%S.%fZ")
            datetime_local = utc_to_local(datetime_utc)
            results[row[0]] = {
                "DATE_LOCAL": datetime_local.strftime("%m/%d/%Y"),
                "TIME_LOCAL": datetime_local.strftime("%H:%M:%S"),
                "LATITUDE_WGS84": row[2],
                "LONGITUDE_WGS84": row[3],
                "UTM8_EASTING": row[4],
                "UTM8_NORTHING": row[5],
                "SPEED": row[6] * 3.6 if row[6] >= 0 else None,
                "BEARING": row[7] if row[7] >= 0 else None,
                "GPS_STATUS": None,
                "SATELLITES": None,
                "HDOP": None,
                "TRACKLOG_ID": row[8],
            }
    return results


def get_track_logs(config):
    """
    Queries an ArcGIS database and returns information on the track logs in it.

    :param config: a dictionary of configuration options
    :return: a dictionary with an integer key (TrackLog_ID), and a dictionary for a value.
    The dictionary contains exactly the string keys:
      'TRANSECT_ID','VESSEL','RECORDER','OBSERVER_1','OBSERVER_2': values are upper case strings,
      'BEAUFORT','WEATHER_CODE','VISIBILITY': values are integers,
      'ON_TRANSECT': value is a string in the set {'TRUE', 'FALSE'}
      'TRACK_LENGTH': value is a floating point number.
    """

    results = {}
    total_length = {}
    features = os.path.join(config["gdb"], "TrackLogs")
    fields = [
        "OID@",
        "Transect",
        "Vessel",
        "Recorder",
        "Observer1",
        "Observer2",
        "Beaufort",
        "Weather",
        "Visibility",
        "Observing",
        "Length_m",
    ]
    with arcpy.da.SearchCursor(features, fields) as cursor:
        for row in cursor:
            # create a total length for all on_transect segments of each transect.
            transect = row[1].upper()
            observing = row[9].upper()
            length = row[10]
            if observing == "YES":
                if transect not in total_length:
                    total_length[transect] = 0
                total_length[transect] += length

            results[row[0]] = {
                "TRANSECT_ID": transect,
                "VESSEL": row[2].upper(),
                "RECORDER": row[3].upper(),
                "OBSERVER_1": row[4].upper(),
                "OBSERVER_2": row[5].upper(),
                "BEAUFORT": row[6],
                "WEATHER_CODE": row[7],
                "VISIBILITY": 3 - row[8],
                "ON_TRANSECT": "TRUE" if observing == "YES" else "FALSE",
                "TRACK_LENGTH": length,
            }
    # apply the total length to all track logs on a transect.
    for key in results:
        transect = results[key]["TRANSECT_ID"]
        track_length = 0
        try:
            track_length = total_length[transect]
        except KeyError:
            arcpy.AddWarning("Transect '{0}' has no total length".format(transect))
        results[key]["TRACK_LENGTH"] = track_length

    return results


def get_observations(config):
    """
    Queries an ArcGIS database and returns information on the observations in it.

    :param config: a dictionary of configuration options
    :return: a dictionary with an integer key (GPSPoint_ID), and a dictionary for a value.
    The dictionary contains exactly the following string keys:
        'ANGLE','DISTANCE': values are integers
    """

    results = {}
    features = os.path.join(config["gdb"], "Observations")
    fields = ["GpsPoint_ID", "Angle", "Distance"]
    with arcpy.da.SearchCursor(features, fields) as cursor:
        for row in cursor:
            results[row[0]] = {"ANGLE": row[1], "DISTANCE": row[2]}
    return results


def get_bird_groups(config):
    """
    Queries an ArcGIS database and returns information on the bird groups in it.

    :param config: a dictionary of configuration options
    :return: a dictionary with an integer key (GPSPoint_ID), and a list of dictionaries for a value.
    The dictionaries contains exactly the following string keys:
        'BEHAVIOR': value is a string in the set {'W', 'F'}
        'GROUP_SIZE': value is an integer
        'SPECIES': value is a string in the set {'K', 'M', 'U', 'P'}
        'COMMENTS': value is an optional string
    """

    results = {}
    features = os.path.join(config["gdb"], "BirdGroups")
    fields = [
        "GpsPoint_ID",
        "countKitlitz",
        "countMarbled",
        "countUnknown",
        "countPending",
        "observedby",
    ]
    with arcpy.da.SearchCursor(features, fields) as cursor:
        for row in cursor:
            groups = []
            template = {"BEHAVIOR": "W", "COMMENTS": None}
            if row[1] > 0:
                group = dict(template)
                group["SPECIES"] = "K"
                group["GROUP_SIZE"] = row[1]
                groups.append(group)
            if row[2] > 0:
                group = dict(template)
                group["SPECIES"] = "M"
                group["GROUP_SIZE"] = row[2]
                groups.append(group)
            if row[3] > 0:
                group = dict(template)
                group["SPECIES"] = "U"
                group["GROUP_SIZE"] = row[3]
                groups.append(group)
            if row[4] > 0:
                group = dict(template)
                group["SPECIES"] = "P"
                group["GROUP_SIZE"] = row[4]
                groups.append(group)
            observer = row[5] if row[5] >= 1 and row[5] <= 2 else None
            results[row[0]] = (groups, observer)
    return results


def open_csv_write(filename):
    """Open file in Python 2/3 compatible way for CSV writing"""
    if sys.version_info[0] < 3:
        return open(filename, "wb")
    return open(filename, "w", encoding="utf8", newline="")


def write_csv_row(writer, row):
    """writer is a csv.writer, and row is a list of unicode or number objects."""
    if sys.version_info[0] < 3:
        # when linted for Python 3, it will not understand unicode
        # pylint: disable=undefined-variable
        writer.writerow(
            [
                item.encode("utf-8") if isinstance(item, unicode) else item
                for item in row
            ]
        )
    else:
        writer.writerow(row)


def create_csv(config):
    """Build the CSV file in accordance with the config object."""

    # pylint: disable=too-many-locals
    fields = config["header"].split(",")
    gps_points = get_gps_points(config)
    track_logs = get_track_logs(config)
    observations = get_observations(config)
    bird_groups = get_bird_groups(config)
    with open_csv_write(config["csv"]) as csv_file:
        csv_writer = csv.writer(csv_file)
        write_csv_row(csv_writer, fields)
        for gps_point_id in gps_points:
            gps_point = gps_points[gps_point_id]
            track_log = track_logs[gps_point["TRACKLOG_ID"]]
            row = [
                track_log[fields[0]],
                gps_point[fields[1]],
                gps_point[fields[2]],
                track_log[fields[3]],
                track_log[fields[4]],
                track_log[fields[5]],
                track_log[fields[6]],
                track_log[fields[7]],
                track_log[fields[8]],
                track_log[fields[9]],
                "{0:.6f}".format(gps_point[fields[10]]),
                "{0:.6f}".format(gps_point[fields[11]]),
                "{0:.2f}".format(gps_point[fields[12]]),
                "{0:.2f}".format(gps_point[fields[13]]),
                "{0:.2f}".format(gps_point[fields[14]])
                if gps_point[fields[14]] is not None
                else None,
                "{0:.1f}".format(gps_point[fields[15]])
                if gps_point[fields[15]] is not None
                else None,
                None,
                None,
                None,
                None,
                None,
                track_log[fields[21]],
                config["protocol"],
                gps_point[fields[23]],
                gps_point[fields[24]],
                gps_point[fields[25]],
                "{0:.1f}".format(track_log[fields[26]]),
                None,
                None,
                None,
                None,
            ]
            if gps_point_id in observations:
                observation = observations[gps_point_id]
                row[16] = "{0:.0f}".format(observation[fields[16]])
                row[17] = "{0:.0f}".format(observation[fields[17]])
                groups, observer = bird_groups[gps_point_id]
                row[30] = (
                    None if observer is None else track_log[fields[4 + observer]]
                )  # Observer#1 or Observer#2
                if len(groups) == 0:
                    arcpy.AddWarning(
                        "No Bird Groups for Observation at GPS Point {0}".format(
                            gps_point_id
                        )
                    )
                    write_csv_row(csv_writer, row)
                else:
                    for bird_group in groups:
                        row[18] = bird_group[fields[18]]
                        row[19] = bird_group[fields[19]]
                        row[20] = bird_group[fields[20]]
                        row[27] = bird_group[fields[27]]
                        write_csv_row(csv_writer, row)
            else:
                write_csv_row(csv_writer, row)


def test():
    """Static input values for testing."""
    config = dict(default_config)
    config["gdb"] = r"C:\tmp\bill\kimu_E\SEAN_KIMU_Protocol_v2.gdb"
    config["csv"] = r"c:\tmp\bill\kimu_E\results.csv"
    create_csv(config)


def main():
    """Command line input values for testing."""
    if len(sys.argv) == 3:
        config = dict(default_config)
        config["gdb"] = sys.argv[1]
        config["csv"] = sys.argv[2]
        create_csv(config)
    else:
        print("USAGE: {} /path/to/data.gdb /path/to/output.csv".format(sys.argv[0]))


# Uncomment this section for testing or command line usage
# Unfortunately ArcGIS loads a toolbox as a file not a module
# if __name__ == '__main__':
#     if len(sys.argv) <= 1:
#         test()
#     else:
#         main()

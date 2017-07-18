import sys
import os
import datetime
import calendar
import csv
import arcpy


default_config = {
    'gdb': '',
    'csv': '',
    'protocol': 'KM-2012.1',
    'header': 'TRANSECT_ID,DATE_LOCAL,TIME_LOCAL,VESSEL,RECORDER,OBSERVER_1,OBSERVER_2,' +
              'BEAUFORT,WEATHER_CODE,VISIBILITY,LATITUDE_WGS84,LONGITUDE_WGS84,' +
              'UTM8_EASTING,UTM8_NORTHING,SPEED,BEARING,ANGLE,DISTANCE,BEHAVIOR,' +
              'GROUP_SIZE,SPECIES,ON_TRANSECT,PROTOCOL_ID,GPS_STATUS,SATELLITES,' +
              'HDOP,TRACK_LENGTH,COMMENTS,DATA_QUALITY,DATA_QUALITY_COMMENT'
}


class Toolbox(object):
    """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
    def __init__(self):
        self.label = "KIMU Toolbox"
        self.alias = "KIMU"
        self.description = "A Toolbox for processing KIMU data for SEAN."
        self.tools = [ExportCSV]


# noinspection PyPep8Naming,PyMethodMayBeStatic,PyUnusedLocal
class ExportCSV(object):
    def __init__(self):
        self.label = "FGDB to CSV"
        self.description = ("Creates CSV file compliant with KIMU Protocol version {} "
                            "from a Park Observer Survey FGDB.".format(default_config['protocol']))

    def getParameterInfo(self):
        fgdb = arcpy.Parameter(
            name="fgdb",
            displayName="Survey FGDB",
            direction="Input",
            datatype="DEWorkspace",
            parameterType="Required")
        fgdb.filter.list = ["poz"]
        csv_folder = arcpy.Parameter(
            name="csv_folder",
            displayName="Output Folder",
            direction="Input",
            datatype="DEFolder",
            parameterType="Required")
        csv_file = arcpy.Parameter(
            name="csv_file",
            displayName="CSV Filename",
            direction="Input",
            datatype="String",
            parameterType="Required")

        parameters = [fgdb, csv_folder, csv_file]
        return parameters

    def updateParameters(self, parameters):
        pass

    def updateMessages(self, parameters):
        pass

    def execute(self, parameters, messages):
        config = dict(default_config)
        config['gdb'] = parameters[0].valueAsText
        config['csv'] = os.path.join(parameters[1].valueAsText, parameters[2].valueAsText)
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
      'DATE_LOCAL': value is a string in the format YYYY-MM-DD representing a date
      'TIME_LOCAL': value is a string in the format HH:MM:SS representing a time
      'LATITUDE_WGS84','LONGITUDE_WGS84': values are doubles
      'UTM8_EASTING','UTM8_NORTHING': values are optional doubles
      'SPEED','BEARING': values are optional doubles
      'GPS_STATUS','SATELLITES': values are optional integers
      'HDOP': value is an optional double
      'TRACKLOG_ID': value is an integer
    """

    results = {}
    fc = os.path.join(config['gdb'], 'GpsPoints')
    sr = arcpy.SpatialReference(3715)  # NAD83(NSRS2007) / UTM zone 8N
    fields = ['OID@', 'Timestamp', 'Latitude', 'Longitude', 'Shape@X', 'Shape@Y', 'Speed_mps', 'Course', 'TrackLog_ID']
    with arcpy.da.SearchCursor(fc, fields, None, sr) as cursor:
        for row in cursor:
            datetime_utc = datetime.datetime.strptime(row[1], "%Y-%m-%dT%H:%M:%S.%fZ")
            datetime_local = utc_to_local(datetime_utc)
            results[row[0]] = {
                'DATE_LOCAL': datetime_local.strftime('%Y-%m-%d'),
                'TIME_LOCAL': datetime_local.strftime('%H:%M:%S'),
                'LATITUDE_WGS84': row[2],
                'LONGITUDE_WGS84': row[3],
                'UTM8_EASTING':  row[4],
                'UTM8_NORTHING':  row[5],
                'SPEED': row[6]*3.6 if 0 <= row[6] else None,
                'BEARING': row[7] if 0 <= row[7] else None,
                'GPS_STATUS': None,
                'SATELLITES': None,
                'HDOP': None,
                'TRACKLOG_ID': row[8]
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
    fc = os.path.join(config['gdb'], 'TrackLogs')
    fields = ['OID@', 'Transect', 'Vessel', 'Recorder', 'Observer1', 'Observer2',
              'Beaufort', 'Weather', 'Visibility', 'Observing', 'Length_m']
    with arcpy.da.SearchCursor(fc, fields) as cursor:
        for row in cursor:
            # create a total length for all on_transect segments of each transect.
            transect = row[1].upper()
            observing = row[9].upper()
            length = row[10]
            if observing == 'YES':
                if transect not in total_length:
                    total_length[transect] = 0
                total_length[transect] += length

            results[row[0]] = {
                'TRANSECT_ID': transect,
                'VESSEL': row[2].upper(),
                'RECORDER': row[3].upper(),
                'OBSERVER_1': row[4].upper(),
                'OBSERVER_2': row[5].upper(),
                'BEAUFORT': row[6],
                'WEATHER_CODE': row[7],
                'VISIBILITY': row[8],
                'ON_TRANSECT': 'TRUE' if observing == 'YES' else 'FALSE',
                'TRACK_LENGTH': length
            }
    # apply the total length to all track logs on a transect.
    for key in results:
        transect = results[key]['TRANSECT_ID']
        track_length = 0
        try:
            track_length = total_length[transect]
        except KeyError:
            arcpy.AddWarning("Transect '{0}' has no total length".format(transect))
        results[key]['TRACK_LENGTH'] = track_length

    return results


def get_observations(config):
    """
    Queries an ArcGIS database and returns information on the observations in it.

    :param config: a dictionary of configuration options
    :return: a dictionary with an integer key (GPSPoint_ID), and a dictionary for a value.
    The dictionary contains exactly the following string keys:
        'ANGLE','DISTANCE': values are floating point numbers
    """

    results = {}
    fc = os.path.join(config['gdb'], 'Observations')
    fields = ['GpsPoint_ID', 'Angle', 'Distance']
    with arcpy.da.SearchCursor(fc, fields) as cursor:
        for row in cursor:
            results[row[0]] = {
                'ANGLE': row[1],
                'DISTANCE': row[2]
            }
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
    fc = os.path.join(config['gdb'], 'BirdGroups')
    fields = ['GpsPoint_ID', 'countKitlitz', 'countMarbled', 'countUnknown', 'countPending']
    with arcpy.da.SearchCursor(fc, fields) as cursor:
        for row in cursor:
            groups = []
            template = {
                'BEHAVIOR': 'W',
                'COMMENTS': None
            }
            if 0 < row[1]:
                group = dict(template)
                group['SPECIES'] = 'K'
                group['GROUP_SIZE'] = row[1]
                groups.append(group)
            if 0 < row[2]:
                group = dict(template)
                group['SPECIES'] = 'M'
                group['GROUP_SIZE'] = row[2]
                groups.append(group)
            if 0 < row[3]:
                group = dict(template)
                group['SPECIES'] = 'U'
                group['GROUP_SIZE'] = row[3]
                groups.append(group)
            if 0 < row[4]:
                group = dict(template)
                group['SPECIES'] = 'P'
                group['GROUP_SIZE'] = row[4]
                groups.append(group)
            results[row[0]] = groups
    return results


def create_csv(config):
    fields = config['header'].split(',')
    gps_points = get_gps_points(config)
    track_logs = get_track_logs(config)
    observations = get_observations(config)
    bird_groups = get_bird_groups(config)
    with open(config['csv'], 'wb') as csv_file:
        csv_writer = csv.writer(csv_file,)
        csv_writer.writerow(fields)
        for gps_point_id in gps_points:
            gps_point = gps_points[gps_point_id]
            track_log = track_logs[gps_point['TRACKLOG_ID']]
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
                "{0:.2f}".format(gps_point[fields[14]]),
                "{0:.1f}".format(gps_point[fields[15]]),
                None,
                None,
                None,
                None,
                None,
                track_log[fields[21]],
                config['protocol'],
                gps_point[fields[23]],
                gps_point[fields[24]],
                gps_point[fields[25]],
                "{0:.1f}".format(track_log[fields[26]]),
                None,
                None,
                None
            ]
            if gps_point_id in observations:
                observation = observations[gps_point_id]
                row[16] = observation[fields[16]]
                row[17] = observation[fields[17]]
                groups = bird_groups[gps_point_id]
                if len(groups) == 0:
                    arcpy.AddWarning("No Bird Groups for Observation at GPS Point {0}".format(gps_point_id))
                    csv_writer.writerow(row)
                else:
                    for bird_group in bird_groups[gps_point_id]:
                        row[18] = bird_group[fields[18]]
                        row[19] = bird_group[fields[19]]
                        row[20] = bird_group[fields[20]]
                        row[27] = bird_group[fields[27]]
                        csv_writer.writerow(row)
            else:
                csv_writer.writerow(row)


def test():
    config = dict(default_config)
    config['gdb'] = r'C:\tmp\bill\kimu_E\SEAN_KIMU_Protocol_v2.gdb'
    config['csv'] = r'c:\tmp\bill\kimu_E\results.csv'
    create_csv(config)


def main():
    if len(sys.argv) == 3:
        config = dict(default_config)
        config['gdb'] = sys.argv[1]
        config['csv'] = sys.argv[2]
        create_csv(config)
    else:
        print "USAGE: {} /path/to/data.gdb /path/to/output.csv".format(sys.argv[0])


"""
# Uncomment this section for testing or command line usage
# Unfortunately ArcGIS loads a toolbox as a file not a module
if __name__ == '__main__':
    if len(sys.argv) <= 1:
        test()
    else:
        main()
"""

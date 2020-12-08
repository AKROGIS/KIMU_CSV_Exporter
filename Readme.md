KIMU CSV Exporter
=================

This is an ArcGIS python toolbox geoprocessing tool that exports a protocol specific CSV file
from an Esri file geodatabase (FGDB) created by the NPS Park Observer mobile data collection
tool. This tool is very specific to the Kittlitz's Murrlet Survey Protocol conducted by the
Southeast Alaska Network (SEAN) in Glacier Bay National Park and Preserve (GLBA).

## Build

This tool does not need to be built in order to be used.  However, this tool needs to stay
in sync with the KIMU survey protocol used by Park Observer.  This can usually be done by
editing the configuration parameters at the start of the `KIMUTools.pyt` file.

## Deploy

Just copy the file `KIMUTools.pyt` file to any location accessible by ArcGIS Desktop.
This toolbox is written for python 2.7 and only works with ArcMap or ArcCatalog.

## Using

In ArcMap or ArcCatalog, open the ArcToolbox window, and right click on an open
space to get the context menu.  Select open toolbox and browse to `KIMUTools.pyt`.
Launch the tool `FGDB to CSV` in the `KIMU Toolbox`.  Select the FGDB created
with the [poz2fgdb](https://github.com/AKROGIS/Park-Observer-poz2fgdb)
tool from the `*.poz` file exported from
[Park Observer](https://github.com/AKROGIS/Park-Observer).
Provide an output folder and file name for the CSV and then click OK.

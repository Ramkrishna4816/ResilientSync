"""resilientsync_webots -- adapter between the ResilientSync engine and a Webots (or stand-in) plant.

Pure Python: nothing in this package imports the Webots `controller` module, so it can be
unit-tested and run without Webots.  Only `webots_project/controllers/rs_coordinator`
touches the Webots API.
"""

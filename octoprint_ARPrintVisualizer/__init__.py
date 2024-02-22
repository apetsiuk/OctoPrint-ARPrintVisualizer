# coding=utf-8
from __future__ import absolute_import
import os
import sys
import requests, base64
import time
import flask
import threading
import subprocess
import octoprint.plugin

import numpy as np
OCTO_AR_DIR = '/Users/kanstantsin/workspace/OctoPrint-ARPrintVisualizer/octoprint_ARPrintVisualizer/OctoAR/'  #!!!!!!!!
IMG_LOC = '/Users/kanstantsin/workspace/OctoPrint/images'  # !!!!!!! loc of 1.png

sys.path.append(OCTO_AR_DIR)
from utils import ARUCO_DICT, aruco_display, get_rec_points, get_centre
import argparse
import cv2   # !!!!!!!! important, version required pip install opencv-contrib-python==4.6.0.66, run when Ocotprint venv sourced!!
import sys

# dir = 'images/'
# if not os.path.exists(dir):
#     os.makedirs(dir)


class ARPrintVisualizerPlugin(octoprint.plugin.StartupPlugin,
                              octoprint.plugin.ShutdownPlugin,
                              octoprint.plugin.SettingsPlugin,
                              octoprint.plugin.TemplatePlugin,
                              octoprint.plugin.AssetPlugin,
                              octoprint.plugin.BlueprintPlugin,
                              ):

    def __init__(self):
        self._process = None
        self._thread = None
        self._thread_stop = threading.Event()
        self._cam_server_path = "\OctoAR\\ar_cam.py"
        self.layer_num = 0
        self.img = None

    ##########################################################################################################

    ##~~ StartupPlugin mixin
    def on_startup(self, host, port):
        """
        Starts the AR Cam Flask server on octoprint server startup
        """
        try:
            log_file = open("flask_log.txt", "w")
            script_abs_path = os.path.dirname(__file__) + self._cam_server_path
            self._process = subprocess.Popen([sys.executable, script_abs_path], stdout=log_file, stderr=log_file)

            time.sleep(2)
            if self._process.poll() is None:
                print("Cam server started successfully.")
            else:
                print("Error while starting the Flask server. Check the log file for details.")
            log_file.close()
        except Exception as e:
            self._logger.info("ARPrintVisualizer failed to start")
            self._logger.info(e)
        return

    ##~~ ShutdownPlugin mixin
    def on_shutdown(self):
        """
        Stops the AR Cam Flask server on octoprint server shutdown
        """
        if self._process is not None and self._process.poll() is None:
            self._logger.info("Stopping the cam server...")
            self._process.terminate()
            self._process.wait()

    ##########################################################################################################

    ##~~ TemplatePlugin mixin
    def get_template_configs(self):
        return [
            {
                "type": "settings",
                "template": "ARPrintVisualizer_settings.jinja2",
                "custom_bindings": True
            },
            {
                "type": "tab",
                "template": "ARPrintVisualizer_tab.jinja2",
                "custom_bindings": True
            }
        ]

    ##~~ AssetPlugin mixin
    def get_assets(self):
        return {
            "js": ["js/ARPrintVisualizer.js"],
            "css": ["css/ARPrintVisualizer.css"],
            "less": ["less/ARPrintVisualizer.less"]
        }

    ##########################################################################################################

    ##~~ SettingsPlugin mixin
    def get_settings_defaults(self):
        """
        Returns the initial default settings for the plugin. Can't skip it!
        """
        return dict(
            stream="",
            aruco_dict="DICT_6X6_250",
        )

    ##########################################################################################################

    ##~~ BlueprintPlugin mixin
    @octoprint.plugin.BlueprintPlugin.route("/detection/start", methods=["GET"])
    def start_detection(self):
        """
        Starts the error detection process
        """
        self._logger.info("Starting the error detection process...")

        self._thread_stop.clear()
        if not self._thread or not self._thread.is_alive():
            self._thread = threading.Thread(target=self.error_detection, daemon=True)
            self._thread.start()

        return flask.jsonify("Evaluation started!")


    @octoprint.plugin.BlueprintPlugin.route("/detection/stop", methods=["GET"])
    def stop_detection(self):
        """
        Stops the error detection process
        """
        self._logger.info("Stopping the error detection process...")
        if self._thread is not None and self._thread.is_alive() and not self._thread_stop.is_set():
            self._thread_stop.set()
            self._thread.join()

        return flask.jsonify("Evaluation stopped!")

    @octoprint.plugin.BlueprintPlugin.route("/correct", methods=["GET"])
    def correct_print(self):
        """
        Corrects the print by inserting a patch
        """
        self._logger.info("Correcting the print...")
        #get the current x,y,z position of the print head
        data = self._printer.get_current_data()
        self._logger.info(data)

        self._printer.resume_print()
        return flask.jsonify("Print corrected!")


    ########################################################################################################## Kos' code starts
    @octoprint.plugin.BlueprintPlugin.route("/set-layer-num", methods=["GET"])
    def set_layer_num(self):
        try:
            self.layer_num = flask.request.values["layer"]
        except Exception as e:
            self._logger.info("ARPrintVisualizer error")
            self._logger.info(e)
        return flask.jsonify(layer=f'{self.layer_num}')

    @octoprint.plugin.BlueprintPlugin.route("/get-layer-num", methods=["GET"])
    def get_layer_num(self):
        return flask.jsonify(layer=f'{self.layer_num}')

    @octoprint.plugin.BlueprintPlugin.route("/get-image", methods=["GET"])
    def get_image(self):
        RESOLUTION_FRONT = (853, 480)
        result = ""
        if "imagetype" in flask.request.values:
            im_type = flask.request.values["imagetype"]
            self.img = self.read_img()
            self.img = cv2.resize(self.img, RESOLUTION_FRONT, interpolation=cv2.INTER_AREA)
            retval, buffer = cv2.imencode('.jpg', self.img)
            try:
                result = flask.jsonify(
                    src="data:image/{0};base64,{1}".format(
                        ".jpg",
                        str(base64.b64encode(buffer), "utf-8"))
                )
            except IOError:
                result = flask.jsonify(
                    error="Unable to fetch img"
                )
        return flask.make_response(result, 200)

    @octoprint.plugin.BlueprintPlugin.route("/get-image-proc", methods=["GET"])
    def get_image_proc(self):
        RESOLUTION_FRONT = (853, 480)
        result = ""
        if "imagetype" in flask.request.values:
            im_type = flask.request.values["imagetype"]
            img_proc = self.detect_markers(self.img.copy())
            img_proc = cv2.resize(img_proc, RESOLUTION_FRONT, interpolation=cv2.INTER_AREA)
            retval, buffer = cv2.imencode('.jpg', img_proc)
            try:
                result = flask.jsonify(
                    src="data:image/{0};base64,{1}".format(
                        ".jpg",
                        str(base64.b64encode(buffer), "utf-8"))
                )
            except IOError:
                result = flask.jsonify(
                    error="Unable to fetch img"
                )
        return flask.make_response(result, 200)

    def read_img(self):
        import os
        self.img = cv2.imread(os.path.join(IMG_LOC, f'{self.layer_num}.png'))
        print(self.img[:5,:5, 0])
        return self.img

    def detect_markers(self, image):
        args = {'type':'DICT_6X6_250'}
        h, w, _ = image.shape
        width = 1000
        height = int(width*(h/w))
        frame = cv2.resize(image, (width, height), interpolation=cv2.INTER_CUBIC)
        img_gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

        # verify that the supplied ArUCo tag exists and is supported by OpenCV
        if ARUCO_DICT.get(args["type"], None) is None:
            print(f"ArUCo tag type '{args['type']}' is not supported")
            sys.exit(0)
        # load the ArUCo dictionary, grab the ArUCo parameters, and detect the markers
        print("Detecting '{}' tags....".format(args["type"]))
        arucoDict = cv2.aruco.Dictionary_get(ARUCO_DICT[args["type"]])
        arucoParams = cv2.aruco.DetectorParameters_create()

        corners, ids, rejected = cv2.aruco.detectMarkers(img_gray, arucoDict, parameters=arucoParams)
        detected_markers = cv2.aruco.drawDetectedMarkers(frame, corners, ids)
        camera_matrix = np.load(os.path.join(OCTO_AR_DIR, "calibration_matrix.npy"))
        dist_coeffs = np.load(os.path.join(OCTO_AR_DIR, "distortion_coefficients.npy"))


        points = get_rec_points(corners)
        if points is not None:
            for point in points:
                cv2.circle(frame, tuple(point), 4, (0, 0, 255), -1)
            org_h, org_w = 16.5, 18.5 #in cm
            points_3D = np.array([[-org_w/2, org_h/2, 0], [org_w/2, org_h/2, 0], [org_w/2, -org_h/2, 0], [-org_w/2, -org_h/2, 0]], dtype="double")

            points_2D = points.astype('float32')
            points_3D = points_3D.astype('float32')

            success, rvecs, tvecs = cv2.solvePnP(points_3D, points_2D, camera_matrix, dist_coeffs)

            len = 5 #in cm
            axis = np.float32([[-len/2, -len/2, 0], [-len/2, len/2, 0], [len/2, len/2, 0], [len/2, -len/2, 0],
                                [-len/2, -len/2, len], [-len/2, len/2, len], [len/2, len/2, len],[len/2, -len/2, len]])

            imgpts_2d, jac = cv2.projectPoints(axis, rvecs, tvecs, camera_matrix, dist_coeffs)
            imgpts_2d = np.int32(imgpts_2d).reshape(-1, 2)
            frame = cv2.drawContours(frame, [imgpts_2d[:4]], -1, (255, 0, 0), 2)
            for i, j in zip(range(4), range(4, 8)):
                frame = cv2.line(frame, tuple(imgpts_2d[i]), tuple(imgpts_2d[j]), (255, 0, 0), 2)
            frame = cv2.drawContours(frame, [imgpts_2d[4:]], -1, (255, 0, 0), 2)

        return frame
    ########################################################################################################## Kos' code ends

    ##~~ Main logic
    def error_detection(self):
        """
        Detects errors in the print and returns the error type
        """
        while not self._thread_stop.is_set():
            r = requests.get(f'http://127.0.0.1:27100/snapshot/{self._settings.get(["stream"])}')
            if r.status_code == 200:
                self._logger.info("Snapshot received")
                img = r.content
                with open("snapshot.jpg", "wb") as f:
                    f.write(img)

                prediciton = self.algo_error_detection(img)
                if prediciton is True:
                    self._logger.info("Error detected!")
                    self._printer.pause_print()
                    self._plugin_manager.send_plugin_message(self._identifier, dict(type="error", error="THIS error was detected and the printer is paused! Take necessary action and resume the print."))
                    self._thread_stop.set()

                time.sleep(2)
            else:
                break


    def algo_error_detection(self, img):
        """
        Runs the error detection algorithm on the image
        """



        return True


    ##########################################################################################################

    ##~~ Softwareupdate hook
    def get_update_information(self):
        """
        Define the configuration for your plugin to use with the Software Update
        Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        for details.
        """
        return {
            "ARPrintVisualizer": {
                "displayName": "ARPrintVisualizer",
                "displayVersion": self._plugin_version,

                # version check: github repository
                "type": "github_release",
                "user": "jatin-47",
                "repo": "OctoPrint-ARPrintVisualizer",
                "current": self._plugin_version,

                # update method: pip
                #"pip": "https://github.com/jatin-47/OctoPrint-ARPrintVisualizer/archive/{target_version}.zip",
            }
        }

__plugin_name__ = "AR Print Visualizer"
__plugin_pythoncompat__ = ">=3,<4"  # Only Python 3

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = ARPrintVisualizerPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }

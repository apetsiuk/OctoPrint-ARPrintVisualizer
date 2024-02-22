/*
 * View model for OctoPrint-Arprintvisualizer
 *
 * Author: Jatin Saini
 * License: AGPLv3
 */
$(function() {
    function ArprintvisualizerViewModel(parameters) {
        var self = this;

        self.settingsViewModel = parameters[0];
        self.isDetecting = ko.observable(false);
        self.isErrorDetected = ko.observable(false);
        self.onBeforeBinding = function() {
        }

        self.toggleDetection = function() {
            self.isDetecting(!self.isDetecting());

            if (self.isDetecting()) {
                $("#detection").text("Stop Error Detection");
                $.ajax({
                    url: "/plugin/ARPrintVisualizer/detection/start",
                    type: "GET",
                    dataType: "json",
                    contentType: "application/json; charset=utf-8",
                    success: function(data) {
                        console.log(data);
                    },
                    error: function(error) {
                        console.log(error);
                    }
                });
            } else {
                $("#detection").text("Start Error Detection");
                $.ajax({
                    url: "/plugin/ARPrintVisualizer/detection/stop",
                    type: "GET",
                    dataType: "json",
                    contentType: "application/json; charset=utf-8",
                    success: function(data) {
                        console.log(data);
                    },
                    error: function(error) {
                        console.log(error);
                    }
                });
            }
        }

        self.resume = function() {
            self.isErrorDetected(false);
            $.ajax({
                url: API_BASEURL + "/job",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=utf-8",
                data: JSON.stringify({
                    command: "pause",
                    action: "resume"
                }),
                success: function(data) {
                    console.log(data);
                },
                error: function(error) {
                    console.log(error);
                }
            });
        }

        self.patchResume = function() {
            $.ajax({
                url: "/plugin/ARPrintVisualizer/correct",
                type: "GET",
                dataType: "json",
                contentType: "application/json; charset=utf-8",
                success: function(data) {
                    console.log(data);
                },
                error: function(error) {
                    console.log(error);
                }
            });
            self.isErrorDetected(false);
        }

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "ARPrintVisualizer") {
                return;
            }

            if (data.type == "error") {
                new PNotify({
                    title: 'Error Detected',
                    text: data.error,
                    type: 'error',
                    hide: false
                });

                $("#detection").text("Start Error Detection");
                self.isDetecting(false);
                self.isErrorDetected(true);
            }

        }

        self._headCanvas = document.getElementById('headCanvas');
        self._headCanvas_proc = document.getElementById('headCanvas_proc');

        self._drawImage = function (img, canv, break_cache = false) {
            var ctx = canv.getContext("2d");
            var localimg = new Image();
            localimg.onload = function () {
                var w = localimg.width;
                var h = localimg.height;
                var scale = Math.min(ctx.canvas.clientWidth / w, ctx.canvas.clientHeight / h, 1);
                ctx.drawImage(localimg, 0, 0, w * scale, h * scale);

                // Avoid memory leak. Not certain if this is implemented correctly, but GC seems to free the memory every now and then.
                localimg = undefined;
            };
            if (break_cache) {
                img = img + "?" + new Date().getTime();
            }
            localimg.src = img;
        };

        self._getImage3 = function (imagetype) {
            $.ajax({
                url: PLUGIN_BASEURL + "visualizer/get-image?imagetype=" + imagetype,
                type: "GET",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                // data: JSON.stringify({"sens_thresh" : self.sens_thresh}),
                success: function (response) {
                    console.log('succ');
                    if (response.hasOwnProperty("src")) {
                        self._drawImage(response.src, self._headCanvas);
                    }
                }
            });
        };

        self._getImage4 = function (imagetype) {
            $.ajax({
                url: PLUGIN_BASEURL + "visualizer/get-image-proc?imagetype=" + imagetype,
                type: "GET",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                // data: JSON.stringify({"sens_thresh" : self.sens_thresh}),
                success: function (response) {
                    console.log('succ');
                    if (response.hasOwnProperty("src")) {
                        self._drawImage(response.src, self._headCanvas_proc);
                    }
                }
            });
        };

        self.layer_num = 0
        // document.getElementById("layer").innerHTML = `${0}`;
        self._getPrintLayer = function () {
            $.ajax({
                url: PLUGIN_BASEURL + "visualizer/get-layer-num",
                type: "GET",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                //data: JSON.stringify(data),
                success: function (response) {
                    if (response.hasOwnProperty("layer")) {
                        self.layer_num = response.layer
                        // self.ui_layerInfo(response.layer)
                        document.getElementById("layer").innerHTML = `Layer: ${response.layer}`;
                    }
                    if (response.hasOwnProperty("error")) {
                        response.error;
                    }
                }
            });
        };
        self._getPrintName = function () {
            $.ajax({
                url:  "api/job",
                type: "GET",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                //data: JSON.stringify(data),
                success: function (response) {
                    if (response.hasOwnProperty("job")) {
                        // self.ui_layerInfo(response.layer)
                        document.getElementById("filename").innerHTML = `Filename: ${response.job.file.name}`;
                    }
                    if (response.hasOwnProperty("error")) {
                        response.error;
                    }
                }
            });
        };


        setInterval(function () {
            self._getPrintLayer();
            self._getPrintName();
        }, 1000)

        setInterval(function () {
            self._getImage3('BIM');
        }, 1000)

        setInterval(function () {
            self._getImage4('BIM');
        }, 1000)

    }


    OCTOPRINT_VIEWMODELS.push({
        construct: ArprintvisualizerViewModel,
        dependencies: [ "settingsViewModel"],
        elements: [ "#settings_plugin_ARPrintVisualizer", "#tab_plugin_ARPrintVisualizer"]
    });
});

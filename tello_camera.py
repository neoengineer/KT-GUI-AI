import traitlets
from traitlets.config.configurable import SingletonConfigurable
import atexit
import cv2
import threading
import numpy as np


class TelloCamera(SingletonConfigurable):
    
    value = traitlets.Any() # The .Any() traitlet is used to hold the numpy array 
    
    # config
    width = traitlets.Integer(default_value=224).tag(config=True)
    height = traitlets.Integer(default_value=224).tag(config=True)
    #fps = traitlets.Integer(default_value=21).tag(config=True)
    #capture_width = traitlets.Integer(default_value=3280).tag(config=True)
    #capture_height = traitlets.Integer(default_value=2464).tag(config=True)

    def __init__(self, *args, **kwargs):
        self.value = np.empty((self.height, self.width, 3), dtype=np.uint8)
        super(TelloCamera, self).__init__(*args, **kwargs) # Get an instance of the SingtonConfigurable and call its init

        try:
            # self.cap = cv2.VideoCapture(self._gst_str(), cv2.CAP_GSTREAMER)
            self.cap = cv2.VideoCapture('udp://0.0.0.0:11111',cv2.CAP_FFMPEG)

            re, image = self.cap.read()

            if not re:
                raise RuntimeError('Could not read image from video stream.')

            self.value = image
            self.start()
        except:
            self.stop()
            raise RuntimeError('Error opening video stream.')

        atexit.register(self.stop)

    def _capture_frames(self):
        while True:
            re, image = self.cap.read()
            if re:
                self.value = image
            else:
                break
                    
    def start(self):
#        if not self.cap.isOpened():
#            self.cap.open(self._gst_str(), cv2.CAP_GSTREAMER)
        if not hasattr(self, 'thread') or not self.thread.isAlive():
            self.thread = threading.Thread(target=self._capture_frames)
            self.thread.start()

    def stop(self):
        if hasattr(self, 'cap'):
            self.cap.release()
        if hasattr(self, 'thread'):
            self.thread.join()
            
    def restart(self):
        self.stop()
        self.start()
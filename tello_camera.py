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
        self.started = False
        self.read_lock = threading.Lock()

        try:
            # self.cap = cv2.VideoCapture(self._gst_str(), cv2.CAP_GSTREAMER)
            
            # TODO - tried to prevent buffering, but seems to have no effect, maybe limited by FFMPEG
            # https://stackoverflow.com/questions/16944024/udp-streaming-with-ffmpeg-overrun-nonfatal-option
            self.cap = cv2.VideoCapture('udp://0.0.0.0:11111?overrun_nonfatal=1',cv2.CAP_FFMPEG) 
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

            re, frame = self.cap.read()

            if not re:
                raise RuntimeError('Could not read frame from video stream.')

            self.value = cv2.resize(frame, (300,300),0,0,interpolation=cv2.INTER_AREA)
            self.start()
        
        except cv2.error:
            self.stop()
            raise RuntimeError('Error opening video stream.')

        atexit.register(self.stop)

    def _capture_frames(self):
        while True:
            self._frame_available = self.cap.grab()

    def get_frame(self):
        if self._frame_available:
            re, frame = self._cap.retrieve()
            self._frame_available = False
            return(frame)
        else:
            return(None)
        
                    
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
        
from threading import Thread, Lock
import cv2

class WebcamVideoStream :
    def __init__(self, src = 0, width = 320, height = 240) :
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, width)
        self.stream.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, height)
        (self.grabbed, self.frame) = self.stream.read()
        self.started = False
        self.read_lock = Lock()

    def start(self) :
        if self.started :
            print "already started!!"
            return None
        self.started = True
        self.thread = Thread(target=self.update, args=())
        self.thread.start()
        return self

    def update(self) :
        while self.started :
            (grabbed, frame) = self.stream.read()
            self.read_lock.acquire()
            self.grabbed, self.frame = grabbed, frame
            self.read_lock.release()

    def read(self) :
        self.read_lock.acquire()
        frame = self.frame.copy()
        self.read_lock.release()
        return frame

    def stop(self) :
        self.started = False
        self.thread.join()

    def __exit__(self, exc_type, exc_value, traceback) :
        self.stream.release()

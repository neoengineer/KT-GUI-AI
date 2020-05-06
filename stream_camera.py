import traitlets
from traitlets.config.configurable import SingletonConfigurable
import atexit
import cv2
import threading
import time


class StreamCamera(SingletonConfigurable):
    
    started = traitlets.Bool(default_value=False, read_only=True)

# TODO maybe pass frame as a np array. Keeping it as a np array from the start may be more efficient...
# TODO remove the locs - these will block all threads

    def __init__(self, *args, **kwargs):
        super(StreamCamera, self).__init__(*args, **kwargs) # Get an instance of the SingtonConfigurable and call its init

        self.set_trait('started', False)
        self._frame_available = False
        #self._read_lock = threading.Lock()
        
        self._thread = threading.Thread(target=self._capture_frames, args=())
       
        # TODO - tried to prevent buffering, but seems to have no effect, maybe limited by FFMPEG
        # https://stackoverflow.com/questions/16944024/udp-streaming-with-ffmpeg-overrun-nonfatal-option
        self._cap = cv2.VideoCapture('udp://0.0.0.0:11111?overrun_nonfatal=1',cv2.CAP_FFMPEG) 
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)      
        
        atexit.register(self.stop)

    def start(self) :
        if not self.started :
            self.set_trait('started', True)
            self._thread.start()    

    def stop(self) :
        if self.started:
            self.set_trait('started', False)
            self._thread.join()  
            
    def _capture_frames(self):
        while self.started:
            #self._read_lock.acquire()
            self._frame_available = self._cap.grab()
            #self._read_lock.release()
            #time.sleep(0.03)
            
    def get_frame(self):
        #if self._frame_available:
            #self._read_lock.acquire()
        re, frame = self._cap.retrieve()
            #self._read_lock.release()
            #self._frame_available = False
        return(re, frame)
        #else:
            #return(False, None)

    def __exit__(self, exc_type, exc_value, traceback) :
        self._cap.release()

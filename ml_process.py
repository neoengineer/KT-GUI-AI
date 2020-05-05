import traitlets
from traitlets.config.configurable import SingletonConfigurable
import atexit
import cv2
import threading
import time

from NVidia.object_detection import *


class MLProcess(SingletonConfigurable):
    
    started = traitlets.Bool(default_value=False, read_only=True)
    processed_image = traitlets.Any(default_value=None)

# TODO maybe pass frame as a np array. Keeping it as a np array from the start may be more efficient...

    def __init__(self, tello=None, camera=None, *args, **kwargs):
        super(MLProcess, self).__init__(*args, **kwargs) # Get an instance of the SingtonConfigurable and call its init

        self.set_trait('started', False)
        self.processed_image = None
        self.detections_active = False
        self.tracking_active = False
        self.target_selection = 0
        
        self._camera = camera
        self._tello = tello
        self._thread = threading.Thread(target=self._mlp, args=())
       
        try:
            self.model = ObjectDetector('ssd_mobilenet_v2_v04_coco.engine')
        except:
            print('error loading model')
            raise RuntimeError("The DNN model failed to load")
            #ss_dnn_model_load.value = False
        else:
            #ss_dnn_model_load.value = True    
            print('model loaded')
            #self.value = cv2.resize(frame, (300,300),0,0,interpolation=cv2.INTER_AREA)        
        
        atexit.register(self.stop)

    def start(self) :
        if not self.started :
            self.set_trait('started', True)
            self._thread.start()    

    def stop(self) :
        if self.started:
            self.set_trait('started', False)
            self._thread.join()  
            
    def _mlp(self):
        while self.started:
            rc, frame = self._camera.get_frame()
            
            if rc: # valid frame available
                
                # resize frome for SDD processing
                image = cv2.resize(frame, (300,300),0,0,interpolation=cv2.INTER_AREA)               
                
                if self.detections_active:
                    
                    # compute all detected objects
                    detections = self.model(image)

                    # draw all detections on image
                    #for det in detections[0]:
                    #    bbox = det['bbox']
                    #    cv2.rectangle(image, (int(300 * bbox[0]), int(300 * bbox[1])), (int(300 * bbox[2]), int(300 * bbox[3])), (255, 0, 0), 2)

                    # select detections that match selected class label
                    # matching_detections = []
                    matching_detections = [d for d in detections[0] if d['label'] == self.target_selection]
     
                    # draw all matchings detections on image
                    for det in matching_detections:
                        bbox = det['bbox']
                        cv2.rectangle(image, (int(300 * bbox[0]), int(300 * bbox[1])), (int(300 * bbox[2]), int(300 * bbox[3])), (0, 255, 0), 2)

                    # get detection closest to center of field of view and draw it
                    #det = closest_detection(matching_detections)
                    #if det is not None:
                    #    bbox = det['bbox']
                    #    cv2.rectangle(image, (int(300 * bbox[0]), int(300 * bbox[1])), (int(300 * bbox[2]), int(300 * bbox[3])), (0, 255, 0), 2)                    
                
                self.processed_image = image

            
    def __exit__(self, exc_type, exc_value, traceback) :
        self._cap.release()

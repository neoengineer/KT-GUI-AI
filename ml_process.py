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

    def __init__(self, tello=None, camera=None, *args, **kwargs):
        super(MLProcess, self).__init__(*args, **kwargs) # Get an instance of the SingtonConfigurable and call its init

        # required interface members
        self.set_trait('started', False)
        self.processed_image = None
        self.detections_active = False
        self.tracking_active = False
        self.target_selection = 0
        self.filtered_detections = []
        
        # private members
        self._camera = camera
        self._tello = tello
        self._thread = threading.Thread(target=self._mlp, args=())
       
        try:
            self._model = ObjectDetector('ssd_mobilenet_v2_v04_coco.engine')
        except:
            print('error loading model')
            raise RuntimeError("The DNN model failed to load")
        

    def start(self) :
        if not self.started :
            self.set_trait('started', True)
            self._thread.start()    
            atexit.register(self.stop)

    def stop(self) :
        if self.started:
            self.set_trait('started', False)
            self._thread.join()  

    def _detection_center(self, detection):
        """
        Computes the center x, y coordinates of the ojbect relative to the
        center of the image - 0,0 is the image center
        """
        bbox = detection['bbox']
        center_x = (bbox[0] + bbox[2]) / 2.0 - 0.5
        center_y = (bbox[1] + bbox[3]) / 2.0 - 0.5
        return (center_x, center_y)

    def _detection_area(self, detection):
        """
        Computes the area of the bounding box
        """
        bbox = detection['bbox']
        # area = x lenght * y lenght
        return ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) )

    def _norm(self, vec):
        """Computes the length of the 2D vector"""
        return np.sqrt(vec[0]**2 + vec[1]**2)

    def _closest_detection(self, detections):
        """Finds the detection closest to the image center"""
        closest_detection = None
        for det in detections:
            #center = self._detection_center(det)
            
            if closest_detection is None: # The first box is the closest box
                closest_detection = det
                
            # the box with the shortest vector is the closest to the center
            elif self._norm(self._detection_center(det)) < self._norm(self._detection_center(closest_detection)):
                closest_detection = det
        return closest_detection
        
    def _mlp(self):
        while self.started:
            rc, frame = self._camera.get_frame()
            
            if rc: # valid frame available
                
                # resize frome for SDD processing
                image = cv2.resize(frame, (300,300),0,0,interpolation=cv2.INTER_AREA)               
                
                if self.detections_active:
                    
                    # compute all detected objects
                    detections = self._model(image)

                    # draw all detections on image
                    for det in detections[0]:
                        bbox = det['bbox']
                        cv2.rectangle(image, (int(300 * bbox[0]), int(300 * bbox[1])), (int(300 * bbox[2]), int(300 * bbox[3])), (255, 0, 0), 2)

                    # select detections that match selected class label
                    #filtered_detections = []

                    if self.target_selection >= 0:
                        self.filtered_detections = [d for d in detections[0] if d['label'] == self.target_selection]     
                        
                        # draw all matchings detections on image
                        for det in self.filtered_detections:
                            bbox = det['bbox']
                            cv2.rectangle(image, (int(300 * bbox[0]), int(300 * bbox[1])), (int(300 * bbox[2]), int(300 * bbox[3])), (0, 255, 0), 2)

                        # get detection closest to center of field of view
                        center_det = self._closest_detection(self.filtered_detections)
                        if center_det is not None:
                            
                            bbox = center_det['bbox']
                            cv2.rectangle(image, (int(300 * bbox[0]), int(300 * bbox[1])), (int(300 * bbox[2]), int(300 * bbox[3])), (0, 0, 255), 2) 
                            
                            # if tracking active, center drone on the target object
                            if self.tracking_active:
                                
                                # compute x,z movement to keep the target in the center of the image
                                center_x, center_y = self._detection_center(center_det)
                                
                                if center_x < -0.1:
                                    x_movement = -10
                                elif center_x > 0.1:
                                    x_movement = 10
                                else: x_movement = 0
                                    
                                if center_y < -0.1:
                                    z_movement = 10
                                elif center_y > 0.1:
                                    z_movement = -10
                                else: z_movement = 0
                                
                                # compute y movement to keep constant distance (fixed bounding box area)
                                area = self._detection_area(center_det)
                                
                                if area < 0.04:
                                    y_movement = 10
                                elif area > 0.3:
                                    y_movement = -10
                                else: y_movement = 0
                                
                                self._tello.rc(x_movement, y_movement, z_movement, 0)
                                time.sleep(0.5)
                                
                        else: # lost the target, so stop moving
                            self._tello.rc(0, 0, 0, 0)
                            time.sleep(0.5)
                                                              
                self.processed_image = image

            
    def __exit__(self, exc_type, exc_value, traceback) :
        self._cap.release()

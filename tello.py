import traitlets
from traitlets.config.configurable import SingletonConfigurable
import socket
import atexit
import threading
import time

TelloCmdPort = 8889      # Command and response
TelloStatusPort = 8890   # Status data from the Tello 
        
class Tello(SingletonConfigurable):
    """Wrapper class to interact with the Tello drone."""

    communication_started = traitlets.Bool(default_value=False, read_only=True)
    status_started = traitlets.Bool(default_value=False, read_only=True)
    status_data = traitlets.Unicode(default_value=None, read_only=False)
    response = traitlets.Unicode(default_value=None, read_only=False)
    
    def __init__(self, tello_ip, local_ip, command_timeout=15.0, *args, **kwargs):
        """
        Binds to the local IP/port and puts the Tello into command mode.

        :param tello_ip (str): Tello IP.
        :param local_ip (str): Local IP address to bind.
        :param command_timeout (int|float): Number of seconds to wait for a response to a command.
        """
        super(Tello, self).__init__(*args, **kwargs) # Get an instance of the SingtonConfigurable and call its init
        
        self.set_trait('communication_started', False)
        self.set_trait('status_started', False)
        self.status_data = ''
        self.response = '' 
        self.is_flying = False

        self._last_height = 0
        self._tello_ip = tello_ip
        self._command_response = ''
        self._error_response = ''
        self._command_abort_flag = False
        self._command_timeout = command_timeout

        # create a socket and thread for receiving command replies
        self._cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # socket for sending / receiving commands
        self._cmd_socket.bind((local_ip, TelloCmdPort))
        self._cmd_thread = threading.Thread(target=self._receive_cmd_replies)
        self._cmd_thread.daemon = True
        
        # create a socket and thread for receiving status stream
        self._status_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # socket for receiving status stream
        self._status_socket.bind((local_ip, TelloStatusPort))
        self._status_thread = threading.Thread(target=self._receive_status)
        self._status_thread.daemon = True

        #self._heartbeat_thread = threading.Thread(target=self._maintain_heartbeat)
        #self._heartbeat_thread.daemon = True
        #self._heartbeat_thread.start()


    def __del__(self):
        """Closes the local socket."""
        self._cmd_socket.close()
        self._status_socket.close()
        # ToDo stop all threads
        
    def start_communication(self):
        if not self.communication_started :
            self.set_trait('communication_started', True)
            self._cmd_thread.start() 
            
    def stop_communication(self) :
        if self.communication_started:
            self.set_trait('communication_started', False)
            self._cmd_thread.join()  

    def _receive_cmd_replies(self):
        """ Private Member!!
        Listen for command responses from the Tello.

        Runs as a thread, sets self._command_response to whatever the Tello last returned.
        """
        while self.communication_started:
            try:
                response, ip = self._cmd_socket.recvfrom(1518) # 1518 in other sample code...
                print(response)
            except OSError as msg:
                print ("Caught exception socket.error : %s" % repr(msg))
            else:
                if response == b'ok':
                    self._command_response = response.decode(encoding='utf-8') # converts a byte array to a string               
                else:
                    self._error_response = response.decode(encoding='utf-8') # converts a byte array to a string
                    
    def send_command(self, command):
        """
        Send a command to the Tello and wait for a response.

        :param command: Command to send.
        :return (str): Response from Tello.

        """
        command_ack = False
        
        # trap for communication thread not started
        if not self.communication_started:
            self.response = 'WARNING: Communication service not running'
            return command_ack
            
        print (">> send cmd: {}".format(command))
        self._command_abort_flag = False
        timer = threading.Timer(self._command_timeout, self._set_abort_flag)
        try:
            self._cmd_socket.sendto(command.encode('utf-8'), (self._tello_ip, TelloCmdPort))
        
        except (socket.error, OSError) as msg:
            self.response = 'WARNING: Socket Error!! ' + repr(msg)
    
        else:
            timer.start()
            while True:   # wait while there is no response             
                if self._command_abort_flag:  # break if the command timed out with no response
                    break
                
                temp_response = self._command_response
                if bool(temp_response):
                    break;
            timer.cancel()

            if bool(temp_response): # received a response and maybe an error messgae
                self.response = temp_response + ' - ' + self._error_response
                self._command_response = ''
                self._error_response = ''
                command_ack = True
            else: # no command response received
                self.response = 'WARNING: Timeout - No response!! ' + self._error_response
                command_ack = False
            
        return command_ack

    def _maintain_heartbeat(self):
        """  Private Member!!
        Send a 'command' string every 5 seconds to keep Tello awake.

        Runs as a thread.
        """
        while True:
            self.set_trait('heartbeat_started', False)
            response = self.send_command('command')
            if response == 'ok':
                self.set_trait('heartbeat_started', True)
            time.sleep(5.0)

    def start_status(self):
        if not self.status_started :
            self.set_trait('status_started', True)
            self._status_thread.start() 
            
    def stop_status(self) :
        if self.status_started:
            self.set_trait('status_started', False)
            self._status_thread.join()  
        
    def _receive_status(self):
        """  Private Member!!
        Listen to status packets from the Tello.

        Runs as a thread, sets self.status to whatever the Tello last returned.
        """
        while self.status_started:
            try:
                response, ip = self._status_socket.recvfrom(1518) # 1518 in other sample code...
            except OSError as msg:
                print ("Caught exception socket.error : %s" % repr(msg))
            else:
                self.status_data = response.decode(encoding='utf-8') # converts a byte array to a string      

                
    def _set_abort_flag(self):
        """ Private Member!
        Sets self._abort_flag to True.

        Used by the timer in Tello.send_command() to indicate to that a response
        timeout has occurred.
        """
        self._command_abort_flag = True

    def takeoff(self):
        """
        Initiates take-off.

        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.

        """

        return self.send_command('takeoff')

    def set_speed(self, speed):
        """
        Sets speed.

        This method expects KPH or MPH. The Tello API expects speeds from
        1 to 100 centimeters/second.

        Metric: .1 to 3.6 KPH
        Imperial: .1 to 2.2 MPH

        Args:
            speed (int|float): Speed.

        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.

        """

        speed = float(speed)
        speed = int(round(speed * 27.7778))

        return self.send_command('speed %s' % speed)

    def rotate_cw(self, degrees):
        """
        Rotates clockwise.

        Args:
            degrees (int): Degrees to rotate, 1 to 360.

        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.

        """

        return self.send_command('cw %s' % degrees)

    def rotate_ccw(self, degrees):
        """
        Rotates counter-clockwise.

        Args:
            degrees (int): Degrees to rotate, 1 to 360.

        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.

        """
        return self.send_command('ccw %s' % degrees)

    def flip(self, direction):
        """
        Flips.

        Args:
            direction (str): Direction to flip, 'l', 'r', 'f', 'b'.

        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.

        """

        return self.send_command('flip %s' % direction)

    def get_response(self):
        """
        Returns response of tello.

        Returns:
            int: response of tello.

        """
        response = self._response
        return response

    def get_height(self):
        """Returns height(dm) of tello.

        Returns:
            int: Height(dm) of tello.

        """
        height = self.send_command('height?')
        height = str(height)
        height = filter(str.isdigit, height)
        try:
            height = int(height)
            self._last_height = height
        except:
            height = self._last_height
            pass
        return height

    def get_battery(self):
        """Returns percent battery life remaining.

        Returns:
            int: Percent battery life remaining.

        """
        
        battery = self.send_command('battery?')

        try:
            battery = int(battery)
        except:
            pass

        return battery

    def get_flight_time(self):
        """Returns the number of seconds elapsed during flight.

        Returns:
            int: Seconds elapsed during flight.

        """

        flight_time = self.send_command('time?')

        try:
            flight_time = int(flight_time)
        except:
            pass

        return flight_time

    def get_speed(self):
        """Returns the current speed.

        Returns:
            int: Current speed in KPH or MPH.

        """

        speed = self.send_command('speed?')

        try:
            speed = float(speed)

            if self.imperial is True:
                speed = round((speed / 44.704), 1)
            else:
                speed = round((speed / 27.7778), 1)
        except:
            pass

        return speed

    def land(self):
        """Initiates landing.

        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.

        """

        return self.send_command('land')

    def move(self, direction, distance):
        """Moves in a direction for a distance.

        This method expects meters or feet. The Tello API expects distances
        from 20 to 500 centimeters.

        Metric: .2 to 5 meters
        Imperial: .7 to 16.4 feet

        Args:
            direction (str): Direction to move, 'forward', 'back', 'right' or 'left'.
            distance (int|float): Distance to move.

        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.

        """

        distance = float(distance)
        #distance = int(round(distance * 100))

        return self.send_command('%s %s' % (direction, distance))

    def move_backward(self, distance):
        """Moves backward for a distance.

        See comments for Tello.move().

        Args:
            distance (int): Distance to move.

        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.

        """

        return self.move('back', distance)

    def move_down(self, distance):
        """Moves down for a distance.

        See comments for Tello.move().

        Args:
            distance (int): Distance to move.

        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.

        """

        return self.move('down', distance)

    def move_forward(self, distance):
        """Moves forward for a distance.

        See comments for Tello.move().

        Args:
            distance (int): Distance to move.

        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.

        """
        return self.move('forward', distance)

    def move_left(self, distance):
        """Moves left for a distance.

        See comments for Tello.move().

        Args:
            distance (int): Distance to move.

        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.

        """
        return self.move('left', distance)

    def move_right(self, distance):
        """Moves right for a distance.

        See comments for Tello.move().

        Args:
            distance (int): Distance to move.

        """
        return self.move('right', distance)

    def move_up(self, distance):
        """Moves up for a distance.

        See comments for Tello.move().

        Args:
            distance (int): Distance to move.

        Returns:
            str: Response from Tello, 'OK' or 'FALSE'.

        """

        return self.move('up', distance)

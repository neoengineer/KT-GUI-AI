import traitlets
from traitlets.config.configurable import SingletonConfigurable
import socket
import atexit
import threading
import time

TelloCmdPort = 8889      # Command and response
TelloStatusPort = 8890   # Status data from the Tello 

Short_Command_Timeout = 0.5
Long_Command_Timeout = 15.0

class Tello(SingletonConfigurable):
    """
    Interface class for single Tello drone.
    
    Traitlets:
        command_link_status (Bool): True - command rcvd, False otherwise
        status_link_status (Bool): True - status rcvd, False otherwise
        status_data (Unicode): Decoded UTF-8 Byte string of status data
        response(Unicode): Command Tx response string
    
    Public Attributes:
            is_flying (Bool): True if Takeoff successful, False if Land successful
    """

    command_link_status = traitlets.Bool(default_value=False, read_only=True)
    status_link_status = traitlets.Bool(default_value=False, read_only=True)
    status_data = traitlets.Unicode(default_value=None, read_only=False)
    response = traitlets.Unicode(default_value=None, read_only=False)
    
    def __init__(self, tello_ip, local_ip, *args, **kwargs):
        """
        Creates sockets for the Tello and local ip.

        Parameters:        
            tello_ip (str): Tello IP.
            local_ip (str): Local IP address to bind.
        """
        super(Tello, self).__init__(*args, **kwargs) # Get an instance of the SingtonConfigurable and call its init
        
        self.set_trait('command_link_status', False)
        self.set_trait('status_link_status', False)
        self.status_data = ''
        self.response = '' 
        self.is_flying = False
        
        self._last_height = 0
        self._tello_ip = tello_ip
        #self._command_response = ''
        #self._error_response = ''
        self._command_abort_flag = False
        #self._command_timeout = command_timeout

        # create a socket and thread for sending and receiving commands
        self._cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # socket for sending / receiving commands
        self._cmd_socket.bind((local_ip, TelloCmdPort))
        self._cmd_socket.setblocking(True)
        
        # create a socket and thread for receiving status stream
        self._status_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # socket for receiving status stream
        self._status_socket.bind((local_ip, TelloStatusPort))
        self._status_thread = threading.Thread(target=self._receive_status)
        self._status_thread.daemon = True
        self._status_thread.start()


    def __del__(self):
        """Closes sockets and stops threads."""
        self._cmd_socket.close()
        self._status_socket.close()
        # ToDo stop all threads

    def send_command(self, command, timeout):
        """
        Send a command to the Tello and wait timeout seconds for each of up to two responses.

        Parameters:
            command (str): Command to send
            timeout (float): Seconds to wait for a command response

        Returns:
            Bool: True if command executed, False if command or communication error
            Sets self.response, self.command_link_status
            
        Note: There are several possible responses from the Tello...
            immediate 'ok'
            immediate 'ok' + message
            immediate 'error'
            immediate 'error' + ok
            immediate data (no 'ok', but trailing \r\n in some cases)
            delayed 'ok' on task completion
            nothing at all ( the rc command )
        """

        rc = False
        
        print (">> send cmd: {}".format(command))
        try:
            self._cmd_socket.settimeout(Short_Command_Timeout)
            self._cmd_socket.sendto(command.encode('utf-8'), (self._tello_ip, TelloCmdPort))
        
        except (socket.error, OSError) as msg:
            self.set_trait('command_link_status', False)
            self.response = 'WARNING: Error on send!! ' + repr(msg)
    
        else: # command sent, so wait for a response
            try:
                self._cmd_socket.settimeout(timeout)
                response, ip = self._cmd_socket.recvfrom(1518) # 1518 in other sample code...
                print(response)
 
            except OSError as msg:
                self.set_trait('command_link_status', False)
                self.response = 'WARNING: Error on recv!! ' + repr(msg)
            
            else: # received some response from Tello...
                
                self.response = response.decode(encoding='utf-8') # converts a byte array to a string 
                self.set_trait('command_link_status', True)

                if not response == b'error':
                    rc = True # not an error, so return True            
                
                # listen for a possible second response string
                try:
                    self._cmd_socket.settimeout(Short_Command_Timeout)
                    response, ip = self._cmd_socket.recvfrom(1518) # 1518 in other sample code...
                    print(response)
                    
                except socket.timeout: pass # maybe no seconds response, so timeout exception is ok
                except OSError as msg:
                    self.response += 'WARNING: Error on recv!! ' + repr(msg)
            
                else: # received a second response from Tello, so append it
                    self.response += ' ' + response.decode(encoding='utf-8') # converts a byte array to a string
        
        return rc
        
    def _receive_status(self):
        """  Private Member!!
        Listen to status packets from the Tello.

        Runs as a thread, sets self.status to whatever the Tello last returned.
        """
        while True:
            try:
                response, ip = self._status_socket.recvfrom(1518) # 1518 in other sample code...
            except OSError as msg:
                print ("Caught exception socket.error : %s" % repr(msg))
                self.set_trait('status_link_status', False)
            else:
                self.status_data = response.decode(encoding='utf-8') # converts a byte array to a string 
                self.set_trait('status_link_status', True)

    def command(self):
        """
        Initiates command mode.

        Returns:
            Bool: True if successful, False if error
            Sets self.response
        """
        return self.send_command('command', Short_Command_Timeout)

    def rc(self, a=0, b=0, c=0, d=0):
        """
        Sends the special rc command to set the velocity vectors for the Tello.

        Parameters:
            a (int): left/right (-100 to 100)
            b (int): forward/backward (-100 to 100)
            c (int): up/down (-100 to 100)
            d (int): yaw (-100 to 100)
        Returns:
            Bool: True if successful, False if error
            Sets self.response to empty string or error
            
        Note: The tello DOES NOT return any status after receiving this command. If the 
        Tello is not in flight when the command is received, then it will execute the 
        rc command immedialy after the next takeoff command is received.
        """
        if not self.is_flying:
            return (False)
        
        rc = True
        command = 'rc %s %s %s %s' % (a, b, c, d)
        
        print (">> send cmd: {}".format(command))
        try:
            self._cmd_socket.settimeout(Short_Command_Timeout)
            self._cmd_socket.sendto(command.encode('utf-8'), (self._tello_ip, TelloCmdPort))
        
        except (socket.error, OSError) as msg:
            self.set_trait('command_link_status', False)
            self.response = 'WARNING: Error on send!! ' + repr(msg)
            rc = False

        return rc

    def takeoff(self):
        """
        Initiates takeoff.

        Returns:
            Bool: True if Takeoff successful, False if error
            Sets self.response
        """
        rc = False
        if not self.is_flying:
            rc = self.send_command('takeoff', Long_Command_Timeout)
            if rc:
                self.is_flying = True
        
        else:
            self.response = "WARNING: Tello already flying!"
                    
        return rc

    def land(self):
        """
        Initiates landing.

        Returns:
            Bool: True if Landing successful, False if error
            Sets self.response
        """
        rc = False
        if self.is_flying:
            rc = self.send_command('land', Long_Command_Timeout)
            if rc:
                self.is_flying = False
        
        else:
            self.response = "WARNING: Tello not flying!"
                    
        return rc

    def streamon(self):
        """
        Initiates video streaming mode.

        Returns:
            Bool: True if successful, False if error
            Sets self.response
        """
        return self.send_command('streamon', Short_Command_Timeout)

    def streamoff(self):
        """
        Disables video streaming mode.

        Returns:
            Bool: True if successful, False if error
            Sets self.response
        """
        return self.send_command('streamoff', Short_Command_Timeout)

    def emergency(self):
        """
        Immediately stops all motors.

        Returns:
            Bool: True if successful, False if error
            Sets self.response
        """
        return self.send_command('emergency', Short_Command_Timeout)

    def stop(self):
        """
        Immediately stops movement and hovers Tello.

        Returns:
            Bool: True if successful, False if error
            Sets self.response
        """
        return self.send_command('stop', Short_Command_Timeout)


    def up(self, x):
        """
        Accend to "x" cm.

        Parameters:
            x (int): 20 to 500 distance to move in cm
            
        Returns:
            Bool: True if successful, False if error
            Sets self.response
        """
        return self.send_command('up %s' % x, Long_Command_Timeout)
    
    def down(self, x):
        """
        desend to "x" cm.

        Parameters:
            x (int): 20 to 500 distance to move in cm

        Returns:
            Bool: True if successful, False if error
            Sets self.response
        """
        return self.send_command('down %s' % x, Long_Command_Timeout)
    
    def left(self, x):
        """
        Fly left for "x" cm.

        Parameters:
            x (int): 20 to 500 distance to move in cm
            
        Returns:
            Bool: True if successful, False if error
            Sets self.response
        """
        return self.send_command('left %s' % x, Long_Command_Timeout)
    
    def right(self, x):
        """
        Fly right for "x" cm.

        Parameters:
            x (int): 20 to 500 distance to move in cm
            
        Returns:
            Bool: True if successful, False if error
            Sets self.response
        """
        return self.send_command('right %s' % x, Long_Command_Timeout)
    
    def forward(self, x):
        """
        Fly forward "x" cm.

        Parameters:
            x (int): 20 to 500 distance to move in cm

        Returns:
            Bool: True if successful, False if error
            Sets self.response
        """
        return self.send_command('forward %s' % x, Long_Command_Timeout)
    
    def back(self, x):
        """
        Fly backward "x" cm.

        Parameters:
            x (int): 20 to 500 distance to move in cm

        Returns:
            Bool: True if successful, False if error
            Sets self.response
        """
        return self.send_command('back %s' % x, Long_Command_Timeout)
    
    def cw(self, x):
        """
        Rotate "x" degrees clockwise.

        Parameters:
            x (int): 1 to 360 degrees to rotate
            
        Returns:
            Bool: True if successful, False if error
            Sets self.response
        """
        return self.send_command('cw %s' % x, Long_Command_Timeout)
    
    def ccw(self, x):
        """
        Rotate "x" degrees counterclockwise.

        Parameters:
            x (int): 1 to 360 degrees to rotate

        Returns:
            Bool: True if successful, False if error
            Sets self.response
        """
        return self.send_command('ccw %s' % x, Long_Command_Timeout)
        
    def go(self, x, y, z, speed):
        """
        Fly to x y z at speed(cm/s).

        Parameters:
            x (int): -500 to 500 distance to move in cm
            y (int): -500 to 500 distance to move in cm
            z (int): -500 to 500 distance to move in cm
            speed (int): 10 to 100 distance to move in cm

        Returns:
            Bool: True if successful, False if error
            Sets self.response

        Note: “x”, “y”, and “z” values can’t be set between -20 – 20 simultaneously.
        """
        return self.send_command('go %s %s %s %s' % (x, y, z, speed), Long_Command_Timeout)
    
    
    
    
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


    def get_response(self):
        """
        Returns response of tello.

        Returns:
            int: response of tello.

        """
        response = self.response
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

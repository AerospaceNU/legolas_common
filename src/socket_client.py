import socket
import threading
import time
from queue import Queue

from .connection_handler import RECEIVE_BUFFER_SIZE, ConnectionHandler
from .packet_types import Packet, PacketType


class SocketClient:
    """Implementation of a multithreaded socket client that connects to a server
    and sends and receives packets"""

    def __init__(
        self,
        server_address: str,
        server_port: int,
        outgoing_data: Queue[Packet],
        received_data: Queue[Packet],
        disconnect_retry_interval: float = 1.0,
    ):
        """Construct a SocketClient

        Args:
            server_address: Address of server to connect to
            server_port: Port of server to connect to
            outgoing_data: Queue of data to transmit to server
            received_data: Queue of data received from server
            disconnect_retry_interval: Interval in seconds between connection attempts
                                       to the server. Defaults to 1.0.
        """
        self.server_address = server_address
        self.server_port = server_port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECEIVE_BUFFER_SIZE)

        self.outgoing_data = outgoing_data
        self.received_data = received_data
        self.internal_recv: Queue[Packet] = Queue()
        self.disconnected = True

        self.prev_connection_time = 0
        self.disconnect_retry_interval = disconnect_retry_interval

        self.run_thread = threading.Thread(target=self._run_handler)

        self.stop_event = threading.Event()
        self.handler: ConnectionHandler | None = None

    def run(self):
        """Run the client to start sending and receiving data"""
        self.run_thread.start()

    def shutdown(self):
        """Shut down the client and all associated threads"""
        self.stop_event.set()
        self.run_thread.join()
        self.handler.join()
        try:
            self.client_socket.shutdown(socket.SHUT_RDWR)
            self.client_socket.close()
        except Exception:
            pass

    def _run_handler(self):
        """Main loop to run the client and transmit and receive packets"""
        while not self.stop_event.is_set():
            if self.disconnected:
                if time.time() - self.prev_connection_time > self.disconnect_retry_interval:
                    try:
                        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        self.client_socket.setsockopt(
                            socket.SOL_SOCKET, socket.SO_RCVBUF, RECEIVE_BUFFER_SIZE
                        )
                        self.client_socket.connect((self.server_address, self.server_port))
                        self.disconnected = False
                        self.handler = ConnectionHandler(
                            self.outgoing_data,
                            self.internal_recv,
                            self.client_socket,
                            self.stop_event,
                        )
                        self.handler.start()
                    except Exception:
                        print("Unable to connect to server...")
                        self.prev_connection_time = time.time()
            else:
                if not self.internal_recv.empty():
                    msg = self.internal_recv.get()
                    if msg.packet_type == PacketType.INTERNAL and msg.payload == "CONN_SHUTDOWN":
                        self.disconnected = True
                        try:
                            self.client_socket.shutdown(socket.SHUT_RDWR)
                            self.client_socket.close()
                        except Exception:
                            pass
                    else:
                        self.received_data.put(msg)
                    print(f"Packet time differential is {time.time() - msg.timestamp} seconds")
                    if msg.packet_type == PacketType.INTERNAL:
                        print(f"Received internal: {msg.payload}")
                    elif msg.packet_type == PacketType.CONTROL:
                        print(f"Received control: {msg.payload}")
                    elif msg.packet_type == PacketType.IMAGE:
                        print("Received image")
                    else:
                        print(f"Received ack: {msg.payload}")
            time.sleep(0.00001)

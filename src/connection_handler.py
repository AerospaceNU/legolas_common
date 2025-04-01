import select
import threading
import time
from queue import Queue
from socket import socket

from .packet_types import BROADCAST_DEST, Packet, PacketType

RECEIVE_BUFFER_SIZE = 16 * 1024 * 1024  # 16 MB
TRANSMIT_BUFFER_SIZE = 8 * 1024 * 1024  # 8 MB


class ConnectionHandler:
    """Connection handler to be created for each incoming connection

    Each handler uses a transmit and receive queue to store the outgoing and incoming packets to
    be used by the rest of the application
    """

    def __init__(
        self,
        tx_queue: Queue[Packet],
        rx_queue: Queue[Packet],
        client_socket: socket,
        stop_event: threading.Event,
        socket_data_len: int = RECEIVE_BUFFER_SIZE,
    ) -> None:
        """Construct a ConnectionHandler

        Args:
            tx_queue: Queue of packets to send out to clients
            rx_queue: Queue of packets received from clients
            client_socket: Socket to use to send and receive data
            stop_event: Threading event to signal shutdown to the thread
            socket_data_len: Data length to receive from socket in chunks
        """
        self.tx_queue = tx_queue
        self.rx_queue = rx_queue
        self.stop_event = stop_event

        self.client_socket = client_socket
        self.socket_data_len = socket_data_len

        self.rx_thread = threading.Thread(
            target=self._run_rx,
        )

        self.tx_thread = threading.Thread(
            target=self._run_tx,
        )

        self.recv_bytes: bytes = b""

        self.lock = threading.Lock()
        self.exited = False

    def start(self):
        """Start the transmit and receive threads"""
        self.tx_thread.start()
        self.rx_thread.start()

    def join(self):
        """Join the transmit and receive threads of the connection handler

        This should only be run once the stop event has been signaled
        (i.e. to join the threads when they are shutting down).
        join will block indefinitely if the stop event has not been signaled."""
        self.tx_thread.join()
        self.rx_thread.join()

    def _run_rx(self):
        """Receive thread entrypoint function

        Receives data from the socket and attempts to parse Packets from the received bytes
        """

        while not self.stop_event.is_set():
            try:
                readable, _, _ = select.select([self.client_socket], [], [], 0.1)
                if readable:
                    data = self.client_socket.recv(self.socket_data_len)

                    if not data:
                        break

                    self.recv_bytes += data

                    while True:
                        recv_pkt, remaining = Packet.unpack(self.recv_bytes)
                        if recv_pkt is None:
                            break
                        self.rx_queue.put(recv_pkt)
                        self.recv_bytes = remaining
                time.sleep(0.00001)
            except Exception as e:
                print(f"Error receiving: {e}")

        self.rx_queue.put(Packet(PacketType.INTERNAL, BROADCAST_DEST, "CONN_SHUTDOWN"))
        self.client_socket.close()
        with self.lock:
            self.exited = True

    def _run_tx(self):
        """Transmit thread entrypoint function

        Waits for packets to be added to the transmit queue and then serializes and transmits
        them via the socket
        """
        try:
            while not self.stop_event.is_set():
                with self.lock:
                    if self.exited:
                        break
                while not self.tx_queue.empty():
                    print(f"Queue length: {self.tx_queue.qsize()}")
                    message = self.tx_queue.get()
                    message_bytes = Packet.pack(message)
                    self.client_socket.sendall(message_bytes)
                time.sleep(0.00001)
        except Exception as e:
            # Don't print error if the error was probably associated with
            # the connection ending and we just didn't catch it yet
            if self.exited:
                return
            print(f"Error transmitting: {e}")

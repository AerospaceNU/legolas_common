import socket
import threading
import time
from queue import Queue

from .connection_handler import TRANSMIT_BUFFER_SIZE, ConnectionHandler
from .packet_types import BROADCAST_DEST, Packet, PacketAddress, PacketType


class SocketServer:
    """Implementation of a multithreded socket server for receiving and accepting connections

    The server will spawn a new thread for each incoming connection using a ConnectionHandler
    """

    def __init__(
        self,
        bind_address: str,
        bind_port: int,
        outgoing_data: Queue[Packet],
        received_data: Queue[Packet],
    ):
        """Initialize the server

        Args:
            bind_address: Address to bind to
            bind_port: Port to listen on
            outgoing_data: Queue of outgoing data to transmit to clients
            received_data: Queue of received data from clients
        """
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, TRANSMIT_BUFFER_SIZE)
        self.server_socket.bind((bind_address, bind_port))
        self.server_socket.listen(10)
        self.server_socket.settimeout(0.1)
        print(f"Socket listening on {bind_address}:{bind_port}")
        self.rx_queues: dict[PacketAddress, Queue[Packet]] = {}
        self.tx_queues: dict[PacketAddress, Queue[Packet]] = {}
        self.connection_handlers: dict[PacketAddress, ConnectionHandler] = {}
        self.outgoing_data = outgoing_data
        self.received_data = received_data
        self.new_socket_queue: Queue[tuple[socket.socket, PacketAddress]] = Queue()

        self.stop_event = threading.Event()

        self.socket_accept_thread = threading.Thread(target=self._accept_handler)
        self.run_thread = threading.Thread(target=self._run_handler)

    def run(self):
        """Run the server process"""
        self.socket_accept_thread.start()
        self.run_thread.start()

    def shutdown(self):
        """Shut down the server, stopping all threads and shutting down the socket"""
        self.stop_event.set()
        for handler in self.connection_handlers.values():
            handler.join()
        self.run_thread.join()
        self.socket_accept_thread.join()
        try:
            self.server_socket.shutdown(socket.SHUT_RDWR)
            self.server_socket.close()
        except Exception:
            # The socket state might get closed or something before this happens,
            # so try our best to shut down but ignore any complaints here
            pass

    def _accept_handler(self):
        """Helper thread entrypoint function to listen and accept new socket connections"""
        while not self.stop_event.is_set():
            try:
                conn_socket, address = self.server_socket.accept()
                source = PacketAddress(*address)
                self.new_socket_queue.put((conn_socket, source))
            except TimeoutError:
                # Timeout error just means that no connection requests were made
                pass
            time.sleep(0.00001)

    def _run_handler(self):
        """Main loop to run the server and transmit and receive packets"""
        while not self.stop_event.is_set():
            if not self.new_socket_queue.empty():
                conn_socket, addr = self.new_socket_queue.get()
                tx_queue = Queue()
                rx_queue = Queue()
                self.connection_handlers[addr] = ConnectionHandler(
                    tx_queue, rx_queue, conn_socket, self.stop_event
                )
                self.connection_handlers[addr].start()
                self.tx_queues[addr] = tx_queue
                self.rx_queues[addr] = rx_queue

            remove_addrs = []

            for addr, queue in self.rx_queues.items():
                while not queue.empty():
                    msg = queue.get()
                    if msg.packet_type == PacketType.INTERNAL and msg.payload == "CONN_SHUTDOWN":
                        remove_addrs.append(addr)
                        # Shutdown messages stop here internally and do not get sent
                        # to the receive queue
                        continue
                    # Insert the address the packet came from, which we know internally.
                    msg.packet_address = addr
                    self.received_data.put(msg)
            for addr in remove_addrs:
                del self.rx_queues[addr]
                del self.tx_queues[addr]
            if not self.outgoing_data.empty():
                tx_message = self.outgoing_data.get()
                if tx_message.packet_address == BROADCAST_DEST:
                    for _, queue in self.tx_queues.items():
                        queue.put(tx_message)
                else:
                    try:
                        self.tx_queues[tx_message.packet_address].put(tx_message)
                    except Exception:
                        print(
                            f"Failed to transmit to address {tx_message.packet_address}: "
                            "no matching transmit queue found"
                        )
            time.sleep(0.00001)

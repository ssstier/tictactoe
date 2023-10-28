import socket
import random
import logging
import time
import ssl
import uuid
import signal
import sys
import os
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import select
from tictactoe_pb2 import TicTacToeMessage, MessageType, PlayerType, PlayerShape

logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(sid)s:%(message)s")

class TicTacToeGame:
    def __init__(self, server_reference, sid):
        self.server = server_reference
        self.sid = sid
        self.server.increment_active_games()
        self.is_decremented = False
        self.board = [None] * 9
        self.reset_requests = set()
        self.current_turn = PlayerType.UNKNOWN_PLAYER
        self.player_shapes = {
            PlayerType.PLAYER_1: PlayerShape.UNKNOWN_SHAPE,
            PlayerType.PLAYER_2: PlayerShape.UNKNOWN_SHAPE,
        }
        self.reset_game()

    def reset_game(self):
        self.current_turn = random.choice([PlayerType.PLAYER_1, PlayerType.PLAYER_2])
        player1_shape = random.choice([PlayerShape.X, PlayerShape.O])
        player2_shape = PlayerShape.O if player1_shape == PlayerShape.X else PlayerShape.X
        self.player_shapes = {
            PlayerType.PLAYER_1: player1_shape,
            PlayerType.PLAYER_2: player2_shape,
        }
        self.board = [None] * 9
        self.reset_requests = set()

    def send_message(self, conn, **attributes):
        try:
            msg = TicTacToeMessage(**attributes)
            conn.send(msg.SerializeToString())
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            logging.error(f"Failed to send message: {e}", extra={'sid': self.sid})

    def relay_chat(self, message, other_conn):
        self.send_message(other_conn, type=MessageType.CHAT, content=f"Opponent: {message}")

    def process_reset_request(self, conn1, conn2):
        self.reset_game()
        player1_data = {
            "type": MessageType.RESET_CONFIRMATION,
            "is_your_turn": self.current_turn == PlayerType.PLAYER_1,
            "player_shape": self.player_shapes[PlayerType.PLAYER_1],
        }
        player2_data = {
            "type": MessageType.RESET_CONFIRMATION,
            "is_your_turn": self.current_turn == PlayerType.PLAYER_2,
            "player_shape": self.player_shapes[PlayerType.PLAYER_2],
        }
        self.send_message(conn1, **player1_data)
        self.send_message(conn2, **player2_data)

    def win_check(self) -> int:
        win_conditions = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Horizontal
            [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Vertical
            [0, 4, 8], [2, 4, 6]              # Diagonal
        ]
        for idx, c in enumerate(win_conditions):
            if self.board[c[0]] and self.board[c[0]] == self.board[c[1]] == self.board[c[2]]:
                return idx + 1
        if None in self.board:
            return 0
        else:
            return 9

    def handle_client(self, conn, other_conn, player):
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    raise ConnectionError(f"Player {player} has disconnected.")
                msg = TicTacToeMessage()
                msg.ParseFromString(data)
                if msg.type == MessageType.CHAT:
                    self.relay_chat(msg.content, other_conn)
                elif msg.type == MessageType.RESET_REQUEST:
                    self.reset_requests.add(player)
                    if len(self.reset_requests) == 2:
                        if player == PlayerType.PLAYER_1:
                            self.process_reset_request(conn, other_conn)
                        else:
                            self.process_reset_request(other_conn, conn)
                    else:
                        self.send_message(other_conn, type=MessageType.PLAY_AGAIN)
                elif msg.type == MessageType.MOVE and player == self.current_turn:
                    if self.board[int(msg.content)] is None:
                        self.board[int(msg.content)] = self.player_shapes[player]
                        game_status = self.win_check()
                        if game_status == 0:
                            if player == PlayerType.PLAYER_1:
                                self.current_turn = PlayerType.PLAYER_2
                            else:
                                self.current_turn = PlayerType.PLAYER_1
                        else:
                            self.current_turn = PlayerType.UNKNOWN_PLAYER

                        move_msg_attrs = {
                            "type": MessageType.MOVE,
                            "content": str(msg.content),
                            "player": self.current_turn,
                            "win_type": game_status,
                            "is_your_turn": game_status == 0,
                            "player_shape": self.player_shapes[player],
                        }
                        self.send_message(other_conn, **move_msg_attrs)
                        move_msg_attrs["is_your_turn"] = not move_msg_attrs["is_your_turn"]
                        self.send_message(conn, **move_msg_attrs)
        except ConnectionError as e:
            logging.info(str(e), extra={'sid': self.sid})
            disconnect_msg = "Opponent has disconnected"
            try:
                self.send_message(other_conn, type=MessageType.MESSAGE, content=disconnect_msg)
                other_conn.shutdown(socket.SHUT_RDWR)
                other_conn.close()
            except Exception as ex:
                logging.error(f"Error while handling disconnection: {ex}", 
                              extra={'sid': self.sid})
        except Exception as e:
            logging.error(f"Unexpected error with client: {e}", extra={'sid': self.sid})
        finally:
            if not self.is_decremented:
                self.server.decrement_active_games()
                self.is_decremented = True


class TicTacToeServer:
    def __init__(self):
        self.active_games = 0
        self.max_games = 10
        self.version = "1.0.0"
        self.running = True
        self.logger = logging.getLogger()

    def set_log_level(self, level):
        if level.lower() == 'info':
            self.logger.setLevel(logging.INFO)
            print("Log level has been set to INFO")
        elif level.lower() == 'error':
            self.logger.setLevel(logging.ERROR)
            print("Log level has been set to ERROR")
        elif level.lower() == 'off':
            self.logger.setLevel(logging.CRITICAL)
            print("Logging has been disabled")
        else:
            print("Invalid log level. Available options are 'info', 'error', and 'off'.")

    def increment_active_games(self):
        self.active_games += 1

    def decrement_active_games(self):
        self.active_games -= 1

    def start(self):
        logging.info("Starting Server...", extra={'sid': 'server'})
        player_queue = deque()
        has_logged_max_capacity = False

        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.load_cert_chain(certfile='combined_cert.pem', keyfile='private_key.pem')

        with ThreadPoolExecutor(max_workers=self.max_games * 2) as executor, \
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:

            server_socket = context.wrap_socket(server_socket, server_side=True)
            server_socket.bind(("0.0.0.0", 52423))
            server_socket.listen(5)

            while True:
                if self.active_games >= self.max_games:
                    if not has_logged_max_capacity:
                        logging.info("Server at maximum capacity!", extra={'sid': 'server'})
                        has_logged_max_capacity = True
                    time.sleep(0.1)
                    continue
                else:
                    has_logged_max_capacity = False

                conn, _ = server_socket.accept()

                try:
                    data = conn.recv(1024)
                    msg = TicTacToeMessage()
                    msg.ParseFromString(data)
                    if msg.type == MessageType.VERSION_CHECK:
                        client_version = msg.version
                        response_msg = TicTacToeMessage(type=MessageType.VERSION_CHECK)
                        if client_version != self.version:
                            logging.info(f"Rejecting client with version {client_version}",
                                         extra={'sid': 'server'})
                            response_msg.content = "INVALID"
                            conn.send(response_msg.SerializeToString())
                            conn.close()
                            continue
                        else:
                            response_msg.content = "VALID"
                            conn.send(response_msg.SerializeToString())
                except Exception as e:
                    logging.error(f"Failed to perform version check: {e}", extra={'sid': 'server'})
                    conn.close()
                    continue

                player_queue.append(conn)

                for sock in list(player_queue):
                    try:
                        readable, _, _ = select.select([sock], [], [], 0)
                        if readable:
                            data = sock.recv(1024, socket.MSG_PEEK)
                            if not data:
                                player_queue.remove(sock)
                    except:
                        player_queue.remove(sock)

                while len(player_queue) >= 2 and self.active_games < self.max_games:
                    player1_conn = player_queue.popleft()
                    player2_conn = player_queue.popleft()
                    new_session_id = str(uuid.uuid4())[:8]
                    logging.info(f"Created session {new_session_id}", extra={'sid': 'server'})
                    game_instance = TicTacToeGame(self, new_session_id)
                    game_instance.send_message(player1_conn, type=MessageType.START,
                                               player=PlayerType.PLAYER_1, content=new_session_id)
                    game_instance.send_message(player2_conn, type=MessageType.START,
                                               player=PlayerType.PLAYER_2, content=new_session_id)
                    game_instance.process_reset_request(player1_conn, player2_conn)
                    p1_args = (player1_conn, player2_conn, PlayerType.PLAYER_1)
                    p2_args = (player2_conn, player1_conn, PlayerType.PLAYER_2)
                    executor.submit(game_instance.handle_client, *p1_args)
                    executor.submit(game_instance.handle_client, *p2_args)
        
    def shutdown(self):
        self.running = False
        sys.exit(0)

    def signal_handler(self, sig, frame):
        print()
        logging.info("Gracefully shutting down...", extra={'sid': 'server'})
        os.system('stty sane')
        self.shutdown()


if __name__ == "__main__":
    server = TicTacToeServer()

    signal.signal(signal.SIGINT, server.signal_handler)

    server.start()
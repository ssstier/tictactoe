import tkinter as tk
from tkinter import Canvas, PhotoImage
import pygame
import copy
import random
import logging
import platform
import socket
import ssl
import os
import sys
import threading
from tictactoe_pb2 import TicTacToeMessage, MessageType, PlayerType, PlayerShape

base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
os_type = platform.system()
logging.basicConfig(level=logging.CRITICAL, format="%(asctime)s:%(levelname)s:%(message)s")


class App(tk.Tk):
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        tk.Tk.resizable(self, width=False, height=False)
        tk.Tk.wm_title(self, " Tic-Tac-Toe Online!")
        if os_type == "Windows":
            icon_path = os.path.join(base_path, "icon.ico")
            self.iconbitmap(icon_path)
        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        pygame.mixer.init()

        self.frames = {}
        for F in (Menu, Game):
            frame = F(container)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")
            self.show_frame(Menu)
        

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()
        return frame


class Menu(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)

        bg_image_path = os.path.join(base_path, "images", "bg.png")
        self.bg_image = PhotoImage(file=bg_image_path)

        bg_label = tk.Label(self, image=self.bg_image)
        bg_label.place(relwidth=1, relheight=1)
        
        button_style = {
            "font": ("Helvetica", 14, "bold"),
            "bg": "#2E8B57",
            "fg": "white",
            "activebackground": "#3CB371",
            "activeforeground": "white",
            "relief": "ridge",
            "borderwidth": 2,
            "highlightthickness": 0
        }

        cpu_button = tk.Button(self, text="Play a CPU", padx=10, pady=5,
                               command=lambda: self.select("CPU", Game), **button_style)
        cpu_button.place(x=25, y=225)

        friend_button = tk.Button(self, text="Local Play", padx=10, pady=5,
                                  command=lambda: self.select("LAN", Game), **button_style)
        friend_button.place(x=195, y=225)

        online_button = tk.Button(self, text="Online Mode", padx=10, pady=5,
                                  command=lambda: self.select("IP", Game), **button_style)
        online_button.place(x=365, y=225)

    @staticmethod
    def select(mode, frame):
        game = app.show_frame(frame)
        game.mode = mode
        logging.info(f"Game mode selected: {mode}")
        game.start()

class Game(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)
        self.font_size = 11 if os_type == "Linux" else 14
        self.setup_variables()
        self.setup_canvas()
        self.setup_chat_ui()
        self.layout_chat_ui()
        self.setup_sounds()

    def setup_variables(self):
        self.version = "1.0.0"
        self.waiting_music_started = False
        self.cpu_turn = False
        self.mode = None
        self.client_socket = None
        self.animate_event = None
        self.game_over = False
        self.circle = None
        self.foreground = []
        self.player = None
        self.board = [None] * 9
        self.shape = None
        self.cpu_shape = None
    
    def setup_sounds(self):
        sound_path_chat = os.path.join(base_path, "sounds", "chat.wav")
        self.chat_sound = pygame.mixer.Sound(sound_path_chat)

        sound_path_move = os.path.join(base_path, "sounds", "move_click.wav")
        self.move_sound = pygame.mixer.Sound(sound_path_move)

        sound_path_win = os.path.join(base_path, "sounds", "win.wav")
        self.win_sound = pygame.mixer.Sound(sound_path_win)

        sound_path_lose = os.path.join(base_path, "sounds", "lose.wav")
        self.lose_sound = pygame.mixer.Sound(sound_path_lose)

        sound_path_matchfound = os.path.join(base_path, "sounds", "match_found.wav")
        self.matchfound_sound = pygame.mixer.Sound(sound_path_matchfound)

    def setup_chat_ui(self):
        # Chat UI Components
        self.chat_frame = tk.Frame(self, bg="black")
        
        self.chat_log = tk.Text(self.chat_frame, height=5, width=42, bg="#333333", fg="white",
                                insertbackground="#333333", highlightthickness=1,
                                highlightbackground="#FFFFFF", highlightcolor="#FFFFFF")
        self.chat_log.config(font=("Arial", self.font_size))
        self.chat_log.bind("<FocusIn>", lambda e: self.message_entry.focus_set())
        self.chat_log.insert(tk.END, "Server: https://www.revogg.com")
        self.chat_log.config(state=tk.DISABLED)
        
        self.message_entry = tk.Entry(self.chat_frame, width=25, bg="#333333", fg="white",
                                      insertbackground="white", insertofftime=0, highlightthickness=1,
                                      highlightbackground="#FFFFFF", highlightcolor="#FFFFFF")
        self.message_entry.bind("<Return>", lambda e: self.send_message())
        self.message_entry.config(font=("Arial", self.font_size))

        button_style = {
            "font": ("Arial", self.font_size),
            "highlightthickness": 0,
            "padx": 10,
            "width": 6,
        }

        self.send_button = tk.Button(self.chat_frame, text="Send", 
                                     command=self.send_message, **button_style)
        self.menu_button = tk.Button(self.chat_frame, text="Menu", 
                                     command=lambda: self.reset(menu=True), **button_style)

        
        self.o_symbol = Canvas(self.chat_frame, bg="#000000", height=50, width=50, 
                               highlightthickness=0)
        self.o_shape = self.o_symbol.create_oval(5, 5, 45, 45, outline="Red", width=8)
        
        self.x_symbol = Canvas(self.chat_frame, bg="#000000", height=50, width=50, 
                               highlightthickness=0)
        self.x_shape1 = self.x_symbol.create_line(5, 5, 45, 45, fill="Blue", width=8)
        self.x_shape2 = self.x_symbol.create_line(45, 5, 5, 45, fill="Blue", width=8)
        
        self.waiting_symbol = Canvas(self.chat_frame, bg="#000000", height=60, 
                                     width=60, highlightthickness=0)

    def layout_chat_ui(self):
        self.chat_frame.grid_columnconfigure(0, weight=3)
        self.chat_frame.grid_columnconfigure(1, weight=1)
        
        self.chat_log.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.message_entry.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.send_button.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        self.menu_button.grid(row=0, column=1, sticky="nw", padx=5, pady=5)
        
        self.chat_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.circle_radius = 25
        self.change = 0.30
        self.max_radius = 25
        self.min_radius = 5
        self.circle_x, self.circle_y = 30, 33
        
        self.waiting_circle = self.waiting_symbol.create_oval(
            self.circle_x - self.circle_radius,
            self.circle_y - self.circle_radius,
            self.circle_x + self.circle_radius,
            self.circle_y + self.circle_radius,
            fill="white"
        )

    def animate_circle(self):
        self.circle_radius += self.change
        if self.circle_radius > self.max_radius or self.circle_radius < self.min_radius:
            self.change = -self.change

        self.waiting_symbol.coords(
            self.waiting_circle,
            self.circle_x - self.circle_radius,
            self.circle_y - self.circle_radius,
            self.circle_x + self.circle_radius,
            self.circle_y + self.circle_radius
        )

        self.animate_event = self.after(20, self.animate_circle)
        
    def stop_waiting_music(self):
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.fadeout(500)
        self.waiting_music_started = False


    def setup_canvas(self):
        self.canvas = Canvas(self, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=1)

        self.draw_on_canvas()

        self.init_clickable_areas()

    def draw_on_canvas(self):
        self.canvas.create_line(220, 50, 220, 347, fill="#fb0", width=6)
        self.canvas.create_line(320, 50, 320, 347, fill="#fb0", width=6)
        self.canvas.create_line(120, 147, 420, 147, fill="#fb0", width=6)
        self.canvas.create_line(120, 247, 420, 247, fill="#fb0", width=6)

    def init_clickable_areas(self):
        self.coordinates = [125, -51, 215, 40]
        self.click_box_dict = dict()
        for i in range(9):
            if i in [0, 3, 6]:
                self.coordinates[0] = 125
                self.coordinates[2] = 215
                self.coordinates[1] += 100
                self.coordinates[3] += 100
            else:
                self.coordinates[0] += 100
                self.coordinates[2] += 100
            self.click_box_dict[i] = copy.deepcopy(self.coordinates)
            click_box = self.canvas.create_rectangle(*self.coordinates, fill="black")
            self.canvas.tag_bind(click_box, "<Button-1>", lambda event, j=i: self.clicked(event, j))

    def start_client(self):
        """Start the client and try to connect to the server."""
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket = context.wrap_socket(self.client_socket, 
                                                 server_hostname="tictactoe.revogg.com")
        try:
            self.client_socket.connect(("tictactoe.revogg.com", 52423))

            version_message = TicTacToeMessage(type=MessageType.VERSION_CHECK, version=self.version)
            self.client_socket.send(version_message.SerializeToString())

            threading.Thread(target=self.listen_for_moves, daemon=True).start()
        except (ConnectionRefusedError, ConnectionResetError, ssl.SSLError) as e:
            error_messages = {
                ConnectionRefusedError: "Cannot connect to the server. Ensure server is runnning",
                ConnectionResetError: "Connection was reset. Did the server go down?",
                ssl.SSLError: "SSL Error; possibly with server's certificate or the connection.",
            }
            error_msg = error_messages.get(type(e), f"An unexpected error occurred: {e}")
            logging.error(error_msg)
            self.display_message(f"Error: {error_msg}")


    def listen_for_moves(self):
        """Listen for moves/messages from the server."""
        while True:
            try:
                data = self.client_socket.recv(1024)
                if not data:
                    logging.info("Connection closed by server.")
                    break

                msg = TicTacToeMessage()
                msg.ParseFromString(data)
                self.handle_received_message(msg)

            except socket.error as e:
                logging.error(f"Socket error in listen_for_moves: {e}")
                break
            except Exception as e:
                logging.error(f"Unexpected error in listen_for_moves: {e}")
                break

        # ============== Chat related methods ==============

    def send_message(self):
        """Send a chat message to the server."""
        message = self.message_entry.get().strip()
        if message:
            try:
                self.display_message(f"You: {message}")
                self.message_entry.delete(0, tk.END)
                if self.mode == "IP" and not self.waiting_music_started:
                    chat_message = TicTacToeMessage(type=MessageType.CHAT, content=message)
                    self.client_socket.send(chat_message.SerializeToString())
            except ssl.SSLEOFError:
                logging.error("A disconnection has occured; cannot send message")
            except Exception as e:
                logging.error(f"An unknown error occurred: {e}")

    def display_message(self, message):
        """Display a message in the chat log."""
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.insert(tk.END, f"\n{message}")
        self.chat_log.see(tk.END)
        self.chat_log.update_idletasks()
        self.chat_log.config(state=tk.DISABLED)
        self.chat_sound.play()

    def clear_chat(self):
        """Clear the chat log."""
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.delete(1.0, tk.END)
        self.chat_log.insert(tk.END, "Server: https://www.revogg.com")
        self.chat_log.config(state=tk.DISABLED)

    # ============== Game related methods ==============

    def update_turn_indicator(self, shape, color='default'):
        """Update the turn indicator on the game interface."""
        self.o_symbol.grid_forget()
        self.x_symbol.grid_forget()
        self.waiting_symbol.grid_forget()

        color_map = {
            'default': {'O': 'Red', 'X': 'Blue'},
            'inactive': {'O': 'Gray', 'X': 'Gray'},
            'yellow': {'O': 'Yellow', 'X': 'Yellow'}
        }

        if shape == "O":
            self.o_symbol.itemconfig(self.o_shape, outline=color_map[color]['O'])
            self.o_symbol.grid(row=0, column=1, sticky="s", padx=5, pady=12)
        elif shape == "X":
            self.x_symbol.itemconfig(self.x_shape1, fill=color_map[color]['X'])
            self.x_symbol.itemconfig(self.x_shape2, fill=color_map[color]['X'])
            self.x_symbol.grid(row=0, column=1, sticky="s", padx=5, pady=12)
        elif shape == "C":
            self.waiting_symbol.grid(row=0, column=1, sticky="s", padx=5, pady=12)
            self.animate_circle()
            if not self.waiting_music_started:
                if not pygame.mixer.get_busy():
                    sound_path_waiting = os.path.join(base_path, "sounds", "waiting.wav")
                    pygame.mixer.music.load(sound_path_waiting)
                    pygame.mixer.music.play(-1)
                    self.waiting_music_started = True

    def prompt_play_again(self):
        """Prompt the user if they want to play again."""
        self.play_again_label = tk.Label(
            self.canvas, text="Play again?", font=("Helvetica", "14"), bg="#000000", fg="#FFFFFF")
        self.play_again_label.place(x=0, y=5)
        self.yes_button = tk.Button(self.canvas, font=("Arial", self.font_size), 
                                    text="Yes", command=self.play_again_yes)
        self.yes_button.place(x=25, y=35)

    def play_again_yes(self):
        """Restart the game."""
        self.play_again_label.destroy()
        self.yes_button.destroy()

        try:
            self.reset()
            if self.mode in ["CPU", "LAN"]:
                self.start()
        except ssl.SSLEOFError:
            logging.error("Cannot play again because opponent disconnected")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")

    def start(self):
        """Start the game based on the selected mode."""
        self.game_over = False
        if self.mode == "CPU":
            self.shape, self.cpu_shape = random.choice([("X", "O"), ("O", "X")])
            first = bool(random.randint(0, 1))
            self.update_turn_indicator(self.shape)
            if first:
                self.handle_cpu_move()
        elif self.mode == "LAN":
            self.current_player = random.choice(["X", "O"])
            self.update_turn_indicator(self.current_player)
        elif self.mode == "IP":
            self.start_client()

    def handle_cpu_move(self):
        """Logic for the CPU to make a move."""
        if self.game_over:
            return

        available_moves = [index for index, value in enumerate(self.board) if value is None]
        if available_moves:
            move = random.choice(available_moves)
            self.process_move(move, self.cpu_shape)

    def process_move(self, i, shape):
        """Handle a move, both from the player and the CPU."""
        valid_move = not (self.game_over or self.board[i] is not None or self.cpu_turn)
        if not valid_move:
            return

        self.draw_symbol_on_board(i, shape)

        self.win_check()

        if self.mode == "CPU" and shape == self.shape and not self.game_over:
            self.handle_cpu_move()

    def draw_symbol_on_board(self, i, shape):
        """Draw the symbol (X or O) on the board."""
        if self.board[i]:
            return
        
        self.move_sound.play()
        symbol_location = copy.deepcopy(self.click_box_dict[i])
        symbol_location[0] += 15
        symbol_location[1] += 15
        symbol_location[2] -= 15
        symbol_location[3] -= 15

        if shape == "O":
            self.board[i] = "O"
            oval = self.canvas.create_oval(*symbol_location, outline="Red", width=12)
            self.foreground.append(oval)
        elif shape == "X":
            self.board[i] = "X"
            line1 = self.canvas.create_line(*symbol_location, fill="Blue", width=12)
            self.foreground.append(line1)
            symbol_location[0] += 60
            symbol_location[2] -= 60
            line2 = self.canvas.create_line(*symbol_location, fill="Blue", width=12)
            self.foreground.append(line2)

    def process_lan_move(self, i):
        """Handle a move in LAN mode and toggle the player."""
        valid_move = not (self.game_over or self.board[i] is not None or self.cpu_turn)
        if not valid_move:
            return

        self.draw_symbol_on_board(i, self.current_player)
        self.win_check()

        if not self.game_over:
            if self.current_player == "X":
                self.current_player = "O"
            else:
                self.current_player = "X"
            self.update_turn_indicator(self.current_player)

    def handle_received_message(self, msg):
        """Handle the received message based on its type."""
        handlers = {
            MessageType.START: self.handle_start,
            MessageType.MOVE: self.handle_move,
            MessageType.RESET_CONFIRMATION: self.handle_reset_confirmation,
            MessageType.CHAT: self.handle_chat,
            MessageType.MESSAGE: self.handle_server_message,
            MessageType.PLAY_AGAIN: self.handle_play_again,
            MessageType.VERSION_CHECK: self.handle_version_check
        }
        handler = handlers.get(msg.type)
        if handler:
            handler(msg)
        else:
            logging.warning(f"Received unhandled message type: {msg.type}")

    def handle_start(self, msg):
        """Handle start message."""
        self.player = PlayerType.Name(msg.player)
        logging.info(f"Joined session {msg.content} as {self.player}")
        self.matchfound_sound.play()
        self.stop_waiting_music()

    def handle_move(self, msg):
        """Handle move confirmation message."""
        if msg.is_your_turn:
            self.update_turn_indicator(self.shape)
        else:
            self.update_turn_indicator(self.shape, color="inactive")

        shape_to_draw = "X" if msg.player_shape == PlayerShape.X else "O"
        self.canvas.after(0, self.draw_symbol_on_board, int(msg.content), shape_to_draw)

        if msg.win_type:
            self.game_over = True
            self.prompt_play_again()
            if msg.win_type != 9:
                self.canvas.after(100, lambda: self.win_check(server_win=msg.win_type - 1))
                if msg.is_your_turn:
                    self.win_sound.play()
                    self.display_message("Server: You won!")
                else:
                    self.lose_sound.play()
                    self.display_message("Server: You lost!")


    def handle_reset_confirmation(self, msg):
        """Handle the reset confirmation message."""
        self.shape = "X" if msg.player_shape == PlayerShape.X else "O"
        self.cpu_shape = "O" if self.shape == "X" else "X"
        self._clear_foreground_widgets()

        if msg.is_your_turn:
            self.update_turn_indicator(self.shape)
        else:
            self.update_turn_indicator(self.shape, color="inactive")

        self.game_over = False
        self.board = [None] * 9

    def handle_chat(self, msg):
        """Handle chat message."""
        self.display_message(msg.content)

    def handle_server_message(self, msg):
        """Display server messages."""
        self.display_message("Server: " + msg.content)
    
    def handle_play_again(self, msg):
        self.update_turn_indicator(self.shape, color="yellow")
    
    def handle_version_check(self, msg):
        if msg.content == "VALID":
            self.update_turn_indicator("C")
            self.display_message("Server: Searching for a match...")
        elif msg.content == "INVALID":
            self.display_message("Server: Version mismatch detected! " +
                                 "Please update software at https://www.revogg.com/downloads")
            self.disconnect()
            

    def clicked(self, event, i):
        """Handle a board slot being clicked."""
        logging.info(f"Player clicked on slot {i}")
        if self.mode == "IP" and not self.waiting_music_started:
            try:
                move_message = TicTacToeMessage(type=MessageType.MOVE, content=str(i))
                self.client_socket.send(move_message.SerializeToString())
            except (BrokenPipeError, ssl.SSLEOFError):
                logging.error("Failed to send move: not connected to the server.")
                #self.display_message("Opponent has disconnected.")
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")
                #self.display_message(f"An error occurred: {e}")
        elif self.mode == "CPU":
            self.process_move(i, self.shape)
        elif self.mode == "LAN":
            self.process_lan_move(i)


    def reset(self, menu=False):
        """Reset the game state."""
        if menu:
            app.show_frame(Menu)
            self.clear_chat()

            if self.mode == "IP":
                
                self.disconnect()
                #self.after_cancel(self.animate_event)

                if self.animate_event is not None:
                    self.after_cancel(self.animate_event)
                    self.animate_event = None
                    self.stop_waiting_music()
            
        self._remove_play_again_ui()
        self._clear_foreground_widgets()
        self.update_turn_indicator(None)

        self.game_over = False
        self.board = [None] * 9
        self.cpu_turn = False

        if self.mode == "IP" and not menu:
            reset_message = TicTacToeMessage(type=MessageType.RESET_REQUEST)
            self.client_socket.send(reset_message.SerializeToString())

    def _remove_play_again_ui(self):
        """Remove the UI elements related to playing again."""
        if hasattr(self, "play_again_label"):
            self.play_again_label.destroy()
        if hasattr(self, "yes_button"):
            self.yes_button.destroy()

    def disconnect(self):
        try:
            if self.client_socket:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
                self.client_socket = None
        except OSError as e:
            if e.errno == 107:  # Transport endpoint is not connected
                logging.warning("Attempting to disconnect an already closed socket.")
            else:
                logging.error(f"OS error while disconnecting: {e}")
        except Exception as e:
            logging.error(f"Unexpected error occurred while disconnecting: {e}")


    def _clear_foreground_widgets(self):
        """Clear foreground widgets."""
        for widget in self.foreground:
            self.canvas.delete(widget)
        self.foreground = []

    def win_check(self, server_win=None):
        """Check if there is a winning condition."""
        win_conditions = [
            [0, 1, 2],
            [3, 4, 5],
            [6, 7, 8],  # horizontal
            [0, 3, 6],
            [1, 4, 7],
            [2, 5, 8],  # vertical
            [0, 4, 8],
            [2, 4, 6],  # diagonal
        ]

        lines = [
            [(120, 100, 420, 100)],
            [(120, 200, 420, 200)],
            [(120, 300, 420, 300)],
            [(175, 50, 175, 347)],
            [(270, 50, 270, 347)],
            [(370, 50, 370, 347)],
            [(140, 65, 400, 330)],
            [(130, 330, 410, 60)],
        ]

        if server_win is not None:
            self.draw_win_line(server_win, lines)
            return

        for i, condition in enumerate(win_conditions):
            if self.check_win_condition_met(condition):
                self.draw_win_line(i, lines)
                self.game_over = True
                self.prompt_play_again()

                if self.mode == "CPU":
                    if self.board[condition[0]] == self.shape:
                        self.win_sound.play()
                    else:
                        self.lose_sound.play()
                return

        if None not in self.board:
            self.game_over = True
            self.prompt_play_again()

    def check_win_condition_met(self, condition):
        """Check if the provided win condition is met."""
        return all(self.board[condition[0]] and 
                   self.board[i] == self.board[condition[0]] for i in condition)

    def draw_win_line(self, win_index, lines):
        """Draw the winning line on the board."""
        self.foreground.append(self.canvas.create_line(*lines[win_index], fill="white", width=4))


app = App()
screen_width = int(app.winfo_screenwidth() / 3)
screen_height = int(app.winfo_screenheight() / 5)
app.geometry("533x533+{}+{}".format(screen_width, screen_height))
app.mainloop()

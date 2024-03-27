import tkinter as tk
from datetime import datetime
import openai
import sqlite3
import speech_recognition as sr
from gtts import gTTS
import threading
import time
import pygame
import tempfile
import PyPDF2
from PIL import Image, ImageTk

class AnitaSystem:
    def __init__(self):
        # File paths
        self.anita_instruction = "instruction.txt"
        self.chat_history_file = "chathistory.txt"
        self.orf_file = "orf.txt"
        self.bg_image = "Miku.png"
        #api
        openai.api_key = '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'

        # Initialize speech recognizer and pygame mixer
        self.r = sr.Recognizer()
        self.chooseMic = None
        pygame.mixer.init()

        # Initialize variables
        self.live_transcription = ""
        self.speech_recognition_active = False
        self.anitaInstructions = None
        self.anita_chathistory = None
        self.anita_orfConvertion = None

        # Get current time and date
        self.current_time = datetime.now().strftime("%I:%M:%S %p")
        self.current_date = datetime.now().strftime("%A, %B %d, %Y")
        self.timeDate = f'The current time is {self.current_time} and the date is {self.current_date}'

        # Initialize GUI components
        self.root = tk.Tk()
        self.root.title("Voice Assistant")
        self.window_width, self.window_height = 530, 678
        self.x, self.y = (self.root.winfo_screenwidth() / 2 - self.window_width / 2), (self.root.winfo_screenheight() / 2 - self.window_height / 2)
        self.root.geometry('%dx%d+%d+%d' % (self.window_width, self.window_height, self.x, self.y))
        self.background_image = ImageTk.PhotoImage(Image.open(self.bg_image))
        self.background_label = tk.Label(self.root, image=self.background_image)
        self.background_label.place(relwidth=1, relheight=1)
        self.output_textbox = tk.Text(self.root, height=10, width=50, bg=self.root.cget('bg'), bd=0, highlightthickness=0)
        self.output_textbox.pack(side="bottom")
        self.speak_button = tk.Button(self.root, text="Start Listening", command=self.start_listening)
        self.speak_button.pack(side="bottom")
        
        # Create database connection and cursor
        self.conn = sqlite3.connect('Conversations.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_table()  # Create table if not exists

        # Start GUI main loop
        self.root.mainloop()

    def create_table(self):
        # Create users table if not exists
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                    (id INTEGER PRIMARY KEY, name TEXT, chat TEXT, time TEXT, date TEXT)''')
        self.conn.commit()

    def save_to_database(self, user, anita, time, date):
        try:
            # Insert user and Anita chats
            self.cursor.execute("INSERT INTO users (name, chat, time, date) VALUES (?, ?, ?, ?), (?, ?, ?, ?)",
                                ('User', user, time, date, 'Anita', anita, time, date))
            # Commit changes to database
            self.conn.commit()
            # Update chat history
            self.memoryHandler(self.cursor)
            self.get_chathistory(self.cursor)
        except sqlite3.Error as e:
            print("Error saving to database:", e)

    def memoryHandler(self, cursor):
        try:
            # Execute the SQL query to get the maximum ID
            cursor.execute("SELECT MAX(id) FROM users")
            max_id = cursor.fetchone()[0]

            # Execute the SQL query to get the count of IDs
            cursor.execute("SELECT COUNT(id) FROM users")
            count = cursor.fetchone()[0]

            if max_id is not None and count is not None and count >= 80:
                cursor.execute("DELETE FROM users WHERE id <= ?", (max_id - 80,))
                self.conn.commit()

        except sqlite3.Error as e:
            print("Error in memoryHandler:", e)


    def changeMic(self):
        for index, name in enumerate(sr.Microphone.list_microphone_names()):  # Check available microphones
                print(f"Microphone {index}: {name}")
        self.chooseMic = 1 #default mic

    # Function to read data from a text file
    def AnitaFiledata(self, txtFile):
        try:
            with open(txtFile, 'r') as file:
                return file.read()
        except FileNotFoundError:
            return "File not found."
        except PermissionError:
            return "Permission denied."
        except Exception as e:
            return f"An error occurred: {e}"

    # Function to extract text from a PDF file
    def extract_text_pdf(self, pdf_path):
        text = ""
        try:
            with open(pdf_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text()
        except FileNotFoundError:
            return "File not found."
        
        return text

    # Function to save conversation to the database


    # Function to retrieve chat history from the database and write it to a file
    def get_chathistory(self, cursor):
        cursor.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        with open(self.chat_history_file, 'w') as Wfile:
            instruction = "Study the user chats and preferences:\n"  # Instruction for the chat history data
            Wfile.write(instruction)
            for row in rows:
                Wfile.write(str(row) + '\n')  # Write each row to the file

    # Function to recognize speech
    def recognize_speech(self, recognizer, audio, conn, cursor):
        try:
            # Extract text from ORF PDF
            orf = self.extract_text_pdf("ORF.pdf")
            # Recognize user speech input
            user_speech_input = recognizer.recognize_google(audio)
            self.live_transcription = f"You said: {user_speech_input}"  # User speech
            self.write_to_textbox(self.live_transcription + "\n")

            # Generate response using OpenAI ChatCompletion
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.timeDate},  # Include time and date
                    {"role": "system", "content": self.AnitaFiledata(self.anita_instruction)},  # Instruction
                    {"role": "system", "content": self.AnitaFiledata(self.anita_chathistory)},  # Chat history
                    {"role": "system", "content": self.AnitaFiledata(self.anita_orfConvertion)},  # ORF data
                    {"role": "user", "content": user_speech_input},  # User input
                ],
            )

            response_text = response.choices[0].message["content"]
            self.write_to_textbox(response_text + "\n")
            self.speak_response(response_text)
            self.save_to_database(self.live_transcription, response_text, self.current_time, self.current_date)

        except sr.UnknownValueError:
            print("Could not understand audio")
        except sr.RequestError as e:
            print(f"Could not request results; {e}")

    # Function to write text to the textbox
    def write_to_textbox(self, text):
        self.output_textbox.config(state=tk.NORMAL)
        self.output_textbox.insert(tk.END, text)
        self.output_textbox.config(state=tk.DISABLED)
        self.output_textbox.see(tk.END)

    # Function to speak the response
    def speak_response(self, response_text):
        tts = gTTS(text=response_text, lang='en')

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            temp_file_name = tmp_file.name
            tts.save(temp_file_name)

        pygame.mixer.music.load(temp_file_name)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

        # Stop the playback explicitly
        pygame.mixer.music.stop()

    # Function to start/stop listening
    def start_listening(self):
        self.speak_button.config(text="Listening...")

        # Use try-finally block to ensure microphone resources are released
        try:
            """
            # Check available microphones debug purposes
            for index, name in enumerate(sr.Microphone.list_microphone_names()):  # Check available microphones
                print(f"Microphone {index}: {name}")"""
            with sr.Microphone(device_index=self.chooseMic) as source:  # Use microphone with index 1
                print("Say something...")
                self.r.adjust_for_ambient_noise(source)
                try:
                    audio = self.r.listen(source, timeout=4)
                    threading.Thread(target=self.recognize_speech, args=(self.r, audio, self.conn, self.cursor)).start()
                except sr.WaitTimeoutError:
                    print("Timeout. No speech detected.")
        finally:
            self.speak_button.config(text="Start Listening")

    # Function to run the Anita system
    def anitaRun(self):
        self.root.mainloop()


# Create an instance of AnitaSystem and start the voice assistant
anita_system = AnitaSystem()
anita_system.anitaRun()
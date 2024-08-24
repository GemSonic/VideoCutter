import sys, re
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, QSlider, QFileDialog, QTextEdit, QLabel, QHBoxLayout, QWidget, QSizePolicy, QLineEdit)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtGui import QPainter, QPen, QMouseEvent, QKeyEvent
import vlc
from moviepy.editor import VideoFileClip, concatenate_videoclips
from CutWindow import CutWindow  # Import the CutWindow from CutWindow.py



class MarkerBar(QWidget):
    """Custom widget for displaying markers and cut points as vertical lines with deletion support."""
    def __init__(self, duration, parent, main_window):
        super().__init__(parent)
        self.duration = duration
        self.markers = []  # Store positions of markers or cut points (in seconds)
        self.setMinimumHeight(20)
        self.setMaximumHeight(20)  # Adjust this to control the height of the marker bar
        self.main_window = main_window  # Store the reference to the main window

    def add_marker(self, time_position):
        """Add a marker or cut point to the marker bar."""
        if 0 <= time_position <= self.duration:
            self.markers.append(time_position)
            self.update()

    def remove_marker(self, index):
        """Remove a marker at the given index."""
        if 0 <= index < len(self.markers):
            del self.markers[index]
            self.update()

    def paintEvent(self, event):
        """Custom paint event to draw the markers."""
        painter = QPainter(self)
        pen = QPen(Qt.red, 2)
        painter.setPen(pen)

        # Draw vertical lines at the position of each marker
        for marker in self.markers:
            x_pos = int((marker / self.duration) * self.width())  # Cast to int to avoid float error
            painter.drawLine(x_pos, 0, x_pos, self.height())

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse clicks for marker removal."""
        x = event.x()
        clicked_marker_index = self.find_marker_by_position(x)
        if clicked_marker_index is not None:
            self.remove_marker(clicked_marker_index)
            self.main_window.remove_cut_point(clicked_marker_index)  # Notify the main window to update cut points

    def find_marker_by_position(self, x_position):
        """Find the marker closest to the clicked position."""
        for i, marker in enumerate(self.markers):
            x_pos = int((marker / self.duration) * self.width())
            if abs(x_pos - x_position) < 5:  # Threshold to detect clicks near the marker
                return i
        return None


class VideoEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Video Editor")

        # Video-related variables
        self.video_path = ""
        self.clip = None
        self.cut_points = []
        self.media_player = vlc.MediaPlayer()
        self.playback = False
        self.duration = 0

        # UI components
        self.init_ui()

        # Install event filter for handling space bar for play/pause
        self.installEventFilter(self)

    def init_ui(self):
        widget = QWidget(self)
        self.setCentralWidget(widget)
        layout = QVBoxLayout()

        # Video display widget
        self.video_widget = QVideoWidget(self)
        self.video_widget.setMinimumSize(640, 360)
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.video_widget)

        # Marker bar, pass reference to the main window
        self.marker_bar = MarkerBar(self.duration, self, self)  # Pass self (main window) as reference
        layout.addWidget(self.marker_bar)

        control_layout = QHBoxLayout()

        load_button = QPushButton("Load Video (L)")
        load_button.clicked.connect(self.load_video)
        load_button.setShortcut("L")
        control_layout.addWidget(load_button)

        play_pause_button = QPushButton("Play/Pause (Space)")
        play_pause_button.clicked.connect(self.toggle_play_pause)
        control_layout.addWidget(play_pause_button)

        stop_button = QPushButton("Stop Video")
        stop_button.clicked.connect(self.stop_video)
        control_layout.addWidget(stop_button)
        control_layout.addStretch(1)  # Add stretch to move Cut button to the far right

        add_cut_button = QPushButton("Add Cut Point (C)")
        add_cut_button.clicked.connect(self.add_cut_point)
        add_cut_button.setShortcut("C")
        control_layout.addWidget(add_cut_button)

        # Undo button to undo the last cut/marker
        undo_button = QPushButton("Undo Last Marker")
        undo_button.clicked.connect(self.undo_last_marker)
        control_layout.addWidget(undo_button)

        # Move Cut button to the right and make it red
        cut_button = QPushButton("Cut Video")
        cut_button.setStyleSheet("background-color: lightcoral; color: black;")
        cut_button.clicked.connect(self.open_cut_window)
        control_layout.addStretch(1)  # Add stretch to move Cut button to the far right
        control_layout.addWidget(cut_button)



        layout.addLayout(control_layout)

        # Scrubber (slider for video position)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.sliderMoved.connect(self.scrub_video)
        layout.addWidget(self.slider)

        # Timecode display
        self.timecode_display = QLabel("00:00:00")
        layout.addWidget(self.timecode_display)

        # Manual timecode input and add marker button
        manual_layout = QHBoxLayout()

        self.manual_timecode_input = QLineEdit()
        self.manual_timecode_input.setPlaceholderText("HH:MM:SS or MM:SS or MM:SS:MS")  # Placeholder to guide input format
        manual_layout.addWidget(self.manual_timecode_input)

        add_marker_button = QPushButton("Add Marker at Timecode")
        add_marker_button.clicked.connect(self.add_manual_marker)
        manual_layout.addWidget(add_marker_button)

        layout.addLayout(manual_layout)

        # Manual cut points display
        self.text_edit = QTextEdit()
        layout.addWidget(self.text_edit)

        widget.setLayout(layout)

        # Timer to update the slider and timecode
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_slider)

    def load_video(self):
        """Load the video using both VLC (for playback) and MoviePy (for editing)."""
        self.video_path, _ = QFileDialog.getOpenFileName(self, "Open Video", "", "Video Files (*.mp4 *.avi *.mov)")
        if self.video_path:
            # Load video into VLC player
            media = vlc.Media(self.video_path)
            self.media_player.set_media(media)
            self.media_player.set_hwnd(self.video_widget.winId())  # Set the video widget for VLC

            # Load the video into MoviePy for manipulation
            self.clip = VideoFileClip(self.video_path)
            self.duration = self.clip.duration  # Video duration in seconds
            self.marker_bar.duration = self.duration  # Set the duration for the marker bar

            # Set the slider's range according to the video duration
            self.slider.setMaximum(int(self.duration * 1000))  # Duration in milliseconds
            self.update_timecode_display(0)  # Initialize timecode display

            print(f"Video loaded: {self.video_path}")

    def eventFilter(self, obj, event):
        """Handle space bar keypress for play/pause."""
        if event.type() == QKeyEvent.KeyPress:
            if event.key() == Qt.Key_Space:
                self.toggle_play_pause()
                return True
        return super().eventFilter(obj, event)

    def toggle_play_pause(self):
        """Toggle between play and pause."""
        if self.media_player.is_playing():
            self.pause_video()
        else:
            self.play_video()

    def update_slider(self):
        """Update the slider position based on the current playback time."""
        if self.media_player.is_playing():
            current_time = self.media_player.get_time()  # Get current time in milliseconds
            self.slider.setValue(current_time)
            self.update_timecode_display(current_time / 1000)

    def update_timecode_display(self, seconds):
        """Update the timecode display."""
        timecode = self.convert_seconds_to_timecode(seconds)
        self.timecode_display.setText(timecode)

    def convert_seconds_to_timecode(self, seconds):
        """Convert a time in seconds to an H:M:S:MS format string."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, remainder = divmod(remainder, 60)
        seconds = remainder
        milliseconds = int((seconds - int(seconds)) * 1000)
        return f"{hours:02}:{minutes:02}:{int(seconds):02}:{milliseconds:03}"

    def play_video(self):
        """Play the video using VLC."""
        if self.video_path:
            self.media_player.play()
            self.timer.start(100)  # Update the slider every 100 milliseconds

    def pause_video(self):
        """Pause the video."""
        if self.video_path:
            self.media_player.pause()

    def stop_video(self):
        """Stop the video."""
        if self.video_path:
            self.media_player.stop()
            self.timer.stop()  # Stop updating the slider

    def scrub_video(self, position):
        """Scrub the video to the specified position."""
        if self.video_path:
            self.media_player.set_time(position)  # VLC uses milliseconds
            self.update_timecode_display(position / 1000)

    def add_cut_point(self):
        """Add a cut point at the current time."""
        if not self.clip:
            return
        current_time = self.media_player.get_time() / 1000  # Convert to seconds
        timecode = self.convert_seconds_to_timecode(current_time)  # Convert to timecode format
        self.cut_points.append(current_time)
        self.text_edit.append(f"{timecode}")

        # Add a marker on the marker bar
        self.marker_bar.add_marker(current_time)

    def add_manual_marker(self):
        """Manually add a cut point based on the timecode input."""
        timecode_str = self.manual_timecode_input.text()
        timecode_seconds = self.parse_timecode(timecode_str)
        if timecode_seconds is not None and 0 <= timecode_seconds <= self.clip.duration:
            self.cut_points.append(timecode_seconds)
            timecode_display = self.convert_seconds_to_timecode(timecode_seconds)
            self.text_edit.append(f"Marker added at {timecode_display}")
            self.marker_bar.add_marker(timecode_seconds)
        else:
            self.text_edit.append("Invalid timecode.")

    def parse_timecode(self, timecode_str):
        """Parse a timecode string that can be in HH:MM:SS, MM:SS, or MM:SS:MS format and convert it to seconds."""
        timecode_str = timecode_str.strip()
        if re.match(r"^\d{1,2}:\d{2}:\d{2}:\d{3}$", timecode_str):  # HH:MM:SS:MS format
            hours, minutes, seconds, milliseconds = map(int, timecode_str.split(":"))
            return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
        elif re.match(r"^\d{1,2}:\d{2}:\d{2}$", timecode_str):  # HH:MM:SS format
            hours, minutes, seconds = map(int, timecode_str.split(":"))
            return hours * 3600 + minutes * 60 + seconds
        elif re.match(r"^\d{1,2}:\d{2}:\d{3}$", timecode_str):  # MM:SS:MS format
            minutes, seconds, milliseconds = map(int, timecode_str.split(":"))
            return minutes * 60 + seconds + milliseconds / 1000
        elif re.match(r"^\d{1,2}:\d{2}$", timecode_str):  # MM:SS format
            minutes, seconds = map(int, timecode_str.split(":"))
            return minutes * 60 + seconds
        else:
            return None

    def undo_last_marker(self):
        """Undo the last added marker or cut point."""
        if self.cut_points:
            last_marker = self.cut_points.pop()  # Remove the last cut point
            self.marker_bar.remove_marker(len(self.marker_bar.markers) - 1)  # Remove from marker bar
            self.text_edit.append(f"Removed marker at {self.convert_seconds_to_timecode(last_marker)}")
        else:
            self.text_edit.append("No markers to undo.")

    def remove_cut_point(self, index):
        """Remove a cut point when a marker is clicked for deletion."""
        if 0 <= index < len(self.cut_points):
            removed_time = self.cut_points.pop(index)
            self.text_edit.append(f"Removed marker at {self.convert_seconds_to_timecode(removed_time)}")

    def open_cut_window(self):
        """Open the CutWindow to manage sections of the video."""
        if not self.clip:
            self.text_edit.append("No video loaded.")
            return

        # Pause the main video if it's playing before opening the CutWindow
        was_playing = self.media_player.is_playing()  # Track if the video was playing
        if was_playing:
            self.pause_video()  # Pause the main video

        # Pass the video_path to the CutWindow for preview functionality
        cut_window = CutWindow(self.duration, self.cut_points, self, video_path=self.video_path)

        # Execute the CutWindow and wait for it to close
        cut_window.exec_()  # Open the CutWindow as a modal dialog



if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = VideoEditorApp()
    editor.show()
    sys.exit(app.exec_())

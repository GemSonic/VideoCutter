from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QScrollArea, QHBoxLayout, QPushButton, QLabel, QFrame, QWidget, QLineEdit, QFileDialog)
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtMultimediaWidgets import QVideoWidget
from moviepy.editor import AudioClip, ImageClip, concatenate_audioclips, concatenate_videoclips, VideoFileClip
import vlc

class MarkerBar(QWidget):
    """Custom widget for displaying markers and cut points as vertical lines."""
    def __init__(self, duration, parent=None):
        super().__init__(parent)
        self.duration = duration
        self.markers = []  # Store positions of markers or cut points (in seconds)
        self.setMinimumHeight(20)
        self.setMaximumHeight(20)  # Adjust this to control the height of the marker bar

    def add_marker(self, time_position):
        """Add a marker or cut point to the marker bar."""
        if 0 <= time_position <= self.duration:
            self.markers.append(time_position)
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


class CutWindow(QDialog):
    """Window for video section selection (Keep or Delete) and preview playback."""
    def __init__(self, duration, cut_points, parent=None, video_path=None):
        super().__init__(parent)
        self.setWindowTitle("Cut Sections")

        self.duration = duration
        self.cut_points = cut_points
        self.sections = []  # Will store whether to "Keep" or "Delete" each section
        self.video_path = video_path  # Path to the video file for previewing sections
        self.media_player = vlc.MediaPlayer()

        # Default value for silence between sections
        self.silence_duration = 1  # Default to 1 second
        self.background_image_path = None  # Path to the background image

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Copy of the MarkerBar
        self.marker_bar = MarkerBar(self.duration, self)
        for cut_point in self.cut_points:
            self.marker_bar.add_marker(cut_point)
        layout.addWidget(self.marker_bar)

        # Video preview player
        self.video_widget = QVideoWidget(self)
        self.video_widget.setMinimumSize(640, 360)
        layout.addWidget(self.video_widget)
        self.media_player.set_hwnd(self.video_widget.winId())

        # Add a scroll area for the sections
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Create sections based on cut points
        last_time = 0
        for i, cut_time in enumerate(self.cut_points + [self.duration]):  # Add final section till end of video
            section_frame = QFrame()
            section_layout = QHBoxLayout(section_frame)

            # Display section info
            section_label = QLabel(f"Section {i + 1}: {self.convert_seconds_to_timecode(last_time)} - {self.convert_seconds_to_timecode(cut_time)}")
            section_layout.addWidget(section_label)

            # Add Toggle button (Switch between Keep and Delete) with pastel colors
            toggle_button = QPushButton("Keep")
            toggle_button.setCheckable(True)
            toggle_button.setChecked(True)  # Default is "Keep"
            toggle_button.setStyleSheet("background-color: lightgreen; color: black;")  # Pastel green for Keep
            toggle_button.clicked.connect(lambda _, idx=i, btn=toggle_button: self.toggle_section_choice(idx, btn))
            section_layout.addWidget(toggle_button)

            # Add "Preview Section" button to preview this section
            preview_button = QPushButton("Preview")
            preview_button.clicked.connect(lambda _, start=last_time, end=cut_time: self.preview_section(start, end))
            section_layout.addWidget(preview_button)

            scroll_layout.addWidget(section_frame)
            self.sections.append("keep")  # Default to keeping all sections
            last_time = cut_time

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Stop Button for stopping the preview manually
        stop_button = QPushButton("Stop Preview")
        stop_button.clicked.connect(self.stop_preview)
        layout.addWidget(stop_button)

        # Input for 'Silence Between Sections'
        silence_layout = QHBoxLayout()
        silence_label = QLabel("Silence Between Sections (sec):")
        self.silence_input = QLineEdit(self)
        self.silence_input.setText("1")  # Default value is 1 second
        silence_layout.addWidget(silence_label)
        silence_layout.addWidget(self.silence_input)
        layout.addLayout(silence_layout)

        # Button to import background image
        import_bg_button = QPushButton("Import Background Image")
        import_bg_button.clicked.connect(self.import_background_image)
        layout.addWidget(import_bg_button)

        # OK and Cancel buttons
        button_layout = QHBoxLayout()

        # Full video button
        full_video_button = QPushButton("Cut and Join Sections - Full Video")
        full_video_button.clicked.connect(self.cut_and_join_sections_with_background)  # Method to add background
        button_layout.addWidget(full_video_button)

        # MP3 only button
        mp3_button = QPushButton("Cut and Join Sections - MP3 only")
        mp3_button.clicked.connect(self.cut_and_join_sections_mp3)  # New method for MP3 only
        button_layout.addWidget(mp3_button)

        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject_and_stop_preview)  # Ensure preview stops on cancel
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def import_background_image(self):
        """Import a background image for the video."""
        image_path, _ = QFileDialog.getOpenFileName(self, "Select Background Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if image_path:
            self.background_image_path = image_path
            QMessageBox.information(self, "Background Image", "Background image imported successfully!")

    def toggle_section_choice(self, index, button):
        """Toggle whether to 'Keep' or 'Delete' the section with color change."""
        if button.isChecked():
            self.sections[index] = "keep"
            button.setText("Keep")
            button.setStyleSheet("background-color: lightgreen; color: black;")  # Pastel green for Keep
        else:
            self.sections[index] = "delete"
            button.setText("Delete")
            button.setStyleSheet("background-color: lightcoral; color: black;")  # Pastel red for Delete

    def preview_section(self, start, end):
        """Preview the selected section of the video."""
        if self.video_path:
            # Create a VLC media instance for the section
            media = vlc.Media(self.video_path)
            self.media_player.set_media(media)
            self.media_player.play()

            # Seek to the start of the section
            self.media_player.set_time(int(start * 1000))

            # Set a timer to stop the preview at the end of the section
            QTimer.singleShot(int((end - start) * 1000), self.stop_preview)

    def stop_preview(self):
        """Stop the video preview."""
        if self.media_player.is_playing():
            self.media_player.stop()

    def closeEvent(self, event):
        """Ensure media player stops when the CutWindow is closed."""
        self.stop_preview()  # Stop playback when the window is closed
        event.accept()

    def reject_and_stop_preview(self):
        """Ensure media player stops when the 'Cancel' button is clicked."""
        self.stop_preview()
        self.reject()  # Close the window

    def convert_seconds_to_timecode(self, seconds):
        """Convert seconds to a formatted timecode."""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, remainder = divmod(remainder, 60)
        seconds = remainder
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def get_section_choices(self):
        """Return the choices made for each section."""
        return self.sections

    def get_silence_duration(self):
        """Return the silence duration entered by the user, default to 1 if empty."""
        try:
            silence_duration = float(self.silence_input.text())
            return max(silence_duration, 0)  # Ensure it's non-negative
        except ValueError:
            return 1  # Default to 1 second if the input is invalid

    def cut_and_join_sections_with_background(self):
        """Cut and join sections and apply a background image."""
        self.stop_preview()  # Stop the preview before performing any further actions
        kept_clips = []
        last_time = 0
        silence_duration = self.get_silence_duration()

        # Confirmation dialog before proceeding
        confirm = QMessageBox.question(self, "Confirm Action", "Are you sure you want to save the video with background?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.No:
            return  # Cancel the process

        if not self.background_image_path:
            QMessageBox.warning(self, "Background Image", "Please import a background image before proceeding.")
            return

        # Load the audio from the video using MoviePy
        video = VideoFileClip(self.video_path)
        final_audio_clips = []

        # Gather all sections marked as 'Keep' and process the audio
        for i, cut_time in enumerate(self.cut_points + [self.duration]):
            if self.sections[i] == "keep":
                final_audio_clips.append(video.subclip(last_time, cut_time).audio)
                if i < len(self.cut_points):  # Add silence between sections
                    silence_audio = AudioClip(lambda t: [0], duration=silence_duration)
                    final_audio_clips.append(silence_audio)
            last_time = cut_time

        # Concatenate the audio sections
        final_audio = concatenate_audioclips(final_audio_clips)

        # Generate background video with the specified image
        final_duration = sum([clip.duration for clip in final_audio_clips])  # Calculate the total duration
        background_clip = ImageClip(self.background_image_path, duration=final_duration).set_duration(final_duration).resize((1920, 1080))

        # Set the final audio to the background video
        background_clip = background_clip.set_audio(final_audio)

        # Save the final video
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Video", "", "MP4 Files (*.mp4)")
        if save_path:
            background_clip.write_videofile(save_path, fps=24, codec="libx264", audio=True)


    def cut_and_join_sections_mp3(self):
        """Cut and join only the audio of sections marked as 'Keep'."""
        self.stop_preview()  # Stop the preview before performing any further actions
        kept_audio_clips = []
        last_time = 0
        silence_duration = self.get_silence_duration()

        # Confirmation dialog before proceeding
        confirm = QMessageBox.question(self, "Confirm Action", "Are you sure you want to save the audio?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.No:
            return  # Cancel the process

        # Load the video using MoviePy to extract the audio
        video = VideoFileClip(self.video_path)

        # Gather all audio sections marked as 'Keep'
        for i, cut_time in enumerate(self.cut_points + [self.duration]):
            if self.sections[i] == "keep":
                kept_audio_clips.append(video.subclip(last_time, cut_time).audio)
                if i < len(self.cut_points):  # Add silence (audio only) between sections
                    silence_audio = AudioClip(lambda t: [0], duration=silence_duration)  # Generate silent audio
                    kept_audio_clips.append(silence_audio)
            last_time = cut_time

        # Concatenate the kept audio sections
        if kept_audio_clips:
            final_audio_clip = concatenate_audioclips(kept_audio_clips)
            save_path, _ = QFileDialog.getSaveFileName(self, "Save Audio", "", "MP3 Files (*.mp3)")
            if save_path:
                final_audio_clip.write_audiofile(save_path)

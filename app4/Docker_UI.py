#!/usr/bin/env python3
"""
Enhanced Docker Image Manager with Essential Features
Includes: Search, Progress Bars, Disk Monitoring, Credentials, Quick Run
"""

import sys
import os
import json
import subprocess
import requests
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import configparser

from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt5.QtGui import QIcon, QPalette, QColor

# ============================================================================
# Configuration Management
# ============================================================================

class ConfigManager:
    """Manages application configuration and credentials"""
    
    def __init__(self):
        self.config_file = os.path.join(os.path.expanduser("~"), ".docker_manager", "config.ini")
        self.config_dir = os.path.dirname(self.config_file)
        
        # Create config directory if it doesn't exist
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self.create_default_config()
    
    def create_default_config(self):
        """Create default configuration"""
        self.config['Artifactory'] = {
            'registry': 'trialqlk1tc.jfrog.io',
            'repository': 'dockertest-docker',
            'username': '',
            'password': ''  # In production, use keyring for secure storage
        }
        self.config['Local'] = {
            'storage_path': 'D:\\DockerImages',
            'auto_refresh_interval': '300',  # seconds
            'max_concurrent_downloads': '3',
            'cleanup_days': '30'
        }
        self.config['UI'] = {
            'theme': 'light',
            'window_width': '1200',
            'window_height': '800'
        }
        self.save_config()
    
    def save_config(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            self.config.write(f)
    
    def get(self, section, key, fallback=''):
        """Get configuration value"""
        return self.config.get(section, key, fallback=fallback)
    
    def set(self, section, key, value):
        """Set configuration value"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)
        self.save_config()

# ============================================================================
# Download Worker with Progress
# ============================================================================

class DownloadWorker(QThread):
    """Worker thread for downloading with progress updates"""
    progress = pyqtSignal(int, str)  # percent, message
    finished = pyqtSignal(bool, str)
    
    def __init__(self, images, config):
        super().__init__()
        self.images = images
        self.config = config
        self.is_cancelled = False
    
    def run(self):
        """Download images with progress tracking"""
        total_images = len(self.images)
        
        # Login to Docker
        registry = self.config.get('Artifactory', 'registry')
        username = self.config.get('Artifactory', 'username')
        password = self.config.get('Artifactory', 'password')
        repository = self.config.get('Artifactory', 'repository')
        storage = self.config.get('Local', 'storage_path')
        
        login_cmd = f'echo {password} | docker login {registry} -u {username} --password-stdin'
        subprocess.run(login_cmd, shell=True, capture_output=True)
        
        for idx, (image, tag) in enumerate(self.images):
            if self.is_cancelled:
                self.finished.emit(False, "Download cancelled")
                return
            
            # Calculate progress
            base_progress = int((idx / total_images) * 100)
            
            # Update progress
            self.progress.emit(base_progress, f"Downloading {image}:{tag}...")
            
            # Pull image
            full_name = f"{registry}/{repository}/{image}:{tag}"
            pull_cmd = f'docker pull {full_name}'
            result = subprocess.run(pull_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Save to tar
                self.progress.emit(base_progress + 50, f"Saving {image}:{tag} to disk...")
                
                tar_file = os.path.join(storage, f"{image}_{tag}.tar")
                save_cmd = f'docker save -o "{tar_file}" {full_name}'
                subprocess.run(save_cmd, shell=True)
                
                self.progress.emit((idx + 1) * 100 // total_images, f"Completed {image}:{tag}")
            else:
                self.progress.emit(base_progress, f"Failed to download {image}:{tag}")
        
        self.finished.emit(True, f"Downloaded {total_images} images")
    
    def cancel(self):
        """Cancel the download"""
        self.is_cancelled = True

# ============================================================================
# Enhanced Main Application
# ============================================================================

class EnhancedDockerManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.download_worker = None
        self.init_ui()
        self.init_storage()
        self.load_credentials()
        self.setup_auto_refresh()
        self.refresh_all()
    
    def init_storage(self):
        """Initialize storage directory"""
        storage_path = self.config.get('Local', 'storage_path')
        if not os.path.exists(storage_path):
            os.makedirs(storage_path)
    
    def init_ui(self):
        """Initialize enhanced UI"""
        self.setWindowTitle("Enhanced Docker Image Manager")
        
        # Load window size from config
        width = int(self.config.get('UI', 'window_width', fallback='1200'))
        height = int(self.config.get('UI', 'window_height', fallback='800'))
        self.setGeometry(100, 100, width, height)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # === Header Section ===
        header_layout = QVBoxLayout()
        
        # Title and connection status
        title_layout = QHBoxLayout()
        title = QLabel("Docker Image Manager")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.connection_status = QLabel("⚫ Disconnected")
        self.connection_status.setStyleSheet("color: gray; font-weight: bold;")
        
        title_layout.addWidget(title)
        title_layout.addStretch()
        title_layout.addWidget(self.connection_status)
        
        header_layout.addLayout(title_layout)
        
        # === Search and Filter Bar ===
        search_layout = QHBoxLayout()
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search images...")
        self.search_input.textChanged.connect(self.filter_table)
        self.search_input.setMinimumWidth(300)
        
        # Filter combo
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Images", "Downloaded", "In Docker", "Not Downloaded", "Large (>500MB)"])
        self.filter_combo.currentTextChanged.connect(self.filter_table)
        
        # Disk space indicator
        self.disk_space_label = QLabel("💾 Calculating...")
        self.update_disk_space()
        
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(QLabel("Filter:"))
        search_layout.addWidget(self.filter_combo)
        search_layout.addStretch()
        search_layout.addWidget(self.disk_space_label)
        
        header_layout.addLayout(search_layout)
        layout.addLayout(header_layout)
        
        # === Toolbar ===
        toolbar_layout = QHBoxLayout()
        
        # Main action buttons
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_all)
        
        self.download_btn = QPushButton("⬇ Download Selected")
        self.download_btn.clicked.connect(self.download_selected)
        
        self.load_btn = QPushButton("📦 Load to Docker")
        self.load_btn.clicked.connect(self.load_to_docker)
        
        self.quick_run_btn = QPushButton("▶ Quick Run")
        self.quick_run_btn.clicked.connect(self.quick_run)
        self.quick_run_btn.setStyleSheet("background-color: #28a745;")
        
        self.remove_btn = QPushButton("❌ Remove from Docker")
        self.remove_btn.clicked.connect(self.remove_from_docker)
        
        self.delete_btn = QPushButton("🗑 Delete Local")
        self.delete_btn.clicked.connect(self.delete_local)
        
        # Selection buttons
        self.select_all_btn = QPushButton("☑ All")
        self.select_all_btn.clicked.connect(self.select_all)
        
        self.select_none_btn = QPushButton("☐ None")
        self.select_none_btn.clicked.connect(self.select_none)
        
        toolbar_layout.addWidget(self.refresh_btn)
        toolbar_layout.addWidget(QLabel(" | "))
        toolbar_layout.addWidget(self.download_btn)
        toolbar_layout.addWidget(self.load_btn)
        toolbar_layout.addWidget(self.quick_run_btn)
        toolbar_layout.addWidget(QLabel(" | "))
        toolbar_layout.addWidget(self.remove_btn)
        toolbar_layout.addWidget(self.delete_btn)
        toolbar_layout.addWidget(QLabel(" | "))
        toolbar_layout.addWidget(self.select_all_btn)
        toolbar_layout.addWidget(self.select_none_btn)
        toolbar_layout.addStretch()
        
        # Settings button
        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.clicked.connect(self.show_settings)
        toolbar_layout.addWidget(self.settings_btn)
        
        layout.addLayout(toolbar_layout)
        
        # === Main Table ===
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Select", "Image", "Tag", "Size", "Created", "Local", "Docker", "Actions"
        ])
        
        # Configure table
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        
        layout.addWidget(self.table)
        
        # === Progress Bar ===
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # === Status Bar ===
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Ready")
        self.auto_refresh_label = QLabel("Auto-refresh: OFF")
        
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.auto_refresh_label)
        
        layout.addLayout(status_layout)
        
        # Apply theme
        self.apply_theme()
    
    def apply_theme(self):
        """Apply UI theme"""
        theme = self.config.get('UI', 'theme', fallback='light')
        
        if theme == 'dark':
            self.setStyleSheet("""
                QMainWindow { background-color: #2b2b2b; }
                QWidget { background-color: #2b2b2b; color: #ffffff; }
                QTableWidget { 
                    background-color: #1e1e1e; 
                    gridline-color: #3c3c3c;
                    selection-background-color: #094771;
                }
                QPushButton { 
                    background-color: #0d7377; 
                    color: white; 
                    border: none; 
                    padding: 8px; 
                    border-radius: 4px; 
                }
                QPushButton:hover { background-color: #14967f; }
                QLineEdit, QComboBox { 
                    background-color: #3c3c3c; 
                    border: 1px solid #555; 
                    padding: 5px; 
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #007bff;
                    color: white;
                    border: none;
                    padding: 8px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #0056b3; }
                QTableWidget { 
                    selection-background-color: #cce5ff;
                    alternate-background-color: #f8f9fa;
                }
            """)
    
    def load_credentials(self):
        """Load saved credentials"""
        username = self.config.get('Artifactory', 'username')
        password = self.config.get('Artifactory', 'password')
        
        if not username or not password:
            self.show_settings()
    
    def setup_auto_refresh(self):
        """Setup auto-refresh timer"""
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.refresh_all)
        
        # Get interval from config (in seconds)
        interval = int(self.config.get('Local', 'auto_refresh_interval', fallback='300'))
        if interval > 0:
            self.auto_refresh_timer.start(interval * 1000)  # Convert to milliseconds
            self.auto_refresh_label.setText(f"Auto-refresh: {interval}s")
    
    def update_disk_space(self):
        """Update disk space indicator"""
        try:
            storage_path = self.config.get('Local', 'storage_path')
            
            # Get disk usage
            total, used, free = shutil.disk_usage(storage_path)
            
            # Calculate Docker images size
            tar_size = sum(
                f.stat().st_size for f in Path(storage_path).glob("*.tar")
            ) if os.path.exists(storage_path) else 0
            
            # Format sizes
            free_gb = free / (1024**3)
            tar_gb = tar_size / (1024**3)
            
            # Update label with color coding
            if free_gb < 10:
                color = "red"
            elif free_gb < 50:
                color = "orange"
            else:
                color = "green"
            
            self.disk_space_label.setText(f"💾 Free: {free_gb:.1f}GB | Images: {tar_gb:.1f}GB")
            self.disk_space_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            
        except Exception as e:
            self.disk_space_label.setText("💾 Unknown")
    
    def refresh_all(self):
        """Refresh all data"""
        self.status_label.setText("Refreshing...")
        self.connection_status.setText("🟡 Connecting...")
        self.connection_status.setStyleSheet("color: orange; font-weight: bold;")
        
        try:
            # Get configuration
            registry = self.config.get('Artifactory', 'registry')
            repository = self.config.get('Artifactory', 'repository')
            username = self.config.get('Artifactory', 'username')
            password = self.config.get('Artifactory', 'password')
            storage = self.config.get('Local', 'storage_path')
            
            # Get catalog from Artifactory
            url = f"https://{registry}/artifactory/api/docker/{repository}/v2/_catalog"
            response = requests.get(url, auth=(username, password), timeout=10)
            
            if response.status_code == 200:
                self.connection_status.setText("🟢 Connected")
                self.connection_status.setStyleSheet("color: green; font-weight: bold;")
                
                data = response.json()
                repos = data.get('repositories', [])
                
                # Clear table
                self.table.setRowCount(0)
                
                for repo in repos:
                    # Get tags
                    tags_url = f"https://{registry}/artifactory/api/docker/{repository}/v2/{repo}/tags/list"
                    tags_response = requests.get(tags_url, auth=(username, password), timeout=10)
                    
                    if tags_response.status_code == 200:
                        tags = tags_response.json().get('tags', ['latest'])
                        
                        for tag in tags:
                            self.add_image_row(repo, tag, registry, repository, storage)
                
                self.status_label.setText(f"Found {self.table.rowCount()} images")
                self.update_disk_space()
            else:
                self.connection_status.setText("🔴 Connection Failed")
                self.connection_status.setStyleSheet("color: red; font-weight: bold;")
                self.status_label.setText("Failed to connect to Artifactory")
                
        except Exception as e:
            self.connection_status.setText("🔴 Error")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
            self.status_label.setText(f"Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to refresh:\n{str(e)}")
    
    def add_image_row(self, image, tag, registry, repository, storage):
        """Add a row to the table"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Checkbox
        checkbox = QCheckBox()
        self.table.setCellWidget(row, 0, checkbox)
        
        # Image name
        self.table.setItem(row, 1, QTableWidgetItem(image))
        
        # Tag
        self.table.setItem(row, 2, QTableWidgetItem(tag))
        
        # Size (placeholder - would need actual manifest data)
        tar_file = os.path.join(storage, f"{image}_{tag}.tar")
        if os.path.exists(tar_file):
            size_mb = os.path.getsize(tar_file) / (1024*1024)
            size_text = f"{size_mb:.1f} MB"
        else:
            size_text = "Unknown"
        self.table.setItem(row, 3, QTableWidgetItem(size_text))
        
        # Created date (placeholder)
        if os.path.exists(tar_file):
            created = datetime.fromtimestamp(os.path.getctime(tar_file)).strftime("%Y-%m-%d")
        else:
            created = "N/A"
        self.table.setItem(row, 4, QTableWidgetItem(created))
        
        # Local file status
        local = "✓" if os.path.exists(tar_file) else "✗"
        local_item = QTableWidgetItem(local)
        local_item.setTextAlignment(Qt.AlignCenter)
        if local == "✓":
            local_item.setForeground(QColor(0, 128, 0))
        self.table.setItem(row, 5, local_item)
        
        # Docker status
        full_name = f"{registry}/{repository}/{image}:{tag}"
        cmd = f'docker images -q {full_name}'
        result = subprocess.run(cmd, shell=True, capture_output=True)
        docker = "✓" if result.stdout.strip() else "✗"
        docker_item = QTableWidgetItem(docker)
        docker_item.setTextAlignment(Qt.AlignCenter)
        if docker == "✓":
            docker_item.setForeground(QColor(0, 0, 255))
        self.table.setItem(row, 6, docker_item)
        
        # Action buttons
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(0, 0, 0, 0)
        
        inspect_btn = QPushButton("🔍")
        inspect_btn.setToolTip("Inspect image")
        inspect_btn.clicked.connect(lambda: self.inspect_image(image, tag))
        inspect_btn.setMaximumWidth(30)
        
        action_layout.addWidget(inspect_btn)
        self.table.setCellWidget(row, 7, action_widget)
    
    def filter_table(self):
        """Filter table based on search and filter criteria"""
        search_text = self.search_input.text().lower()
        filter_type = self.filter_combo.currentText()
        
        for row in range(self.table.rowCount()):
            show_row = True
            
            # Search filter
            if search_text:
                image_name = self.table.item(row, 1).text().lower()
                tag = self.table.item(row, 2).text().lower()
                if search_text not in image_name and search_text not in tag:
                    show_row = False
            
            # Type filter
            if filter_type != "All Images":
                local_status = self.table.item(row, 5).text()
                docker_status = self.table.item(row, 6).text()
                size_text = self.table.item(row, 3).text()
                
                if filter_type == "Downloaded" and local_status != "✓":
                    show_row = False
                elif filter_type == "In Docker" and docker_status != "✓":
                    show_row = False
                elif filter_type == "Not Downloaded" and local_status != "✗":
                    show_row = False
                elif filter_type == "Large (>500MB)":
                    try:
                        size_mb = float(size_text.replace(" MB", ""))
                        if size_mb <= 500:
                            show_row = False
                    except:
                        show_row = False
            
            self.table.setRowHidden(row, not show_row)
    
    def select_all(self):
        """Select all visible rows"""
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                checkbox = self.table.cellWidget(row, 0)
                if checkbox:
                    checkbox.setChecked(True)
    
    def select_none(self):
        """Deselect all rows"""
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)
    
    def get_selected_images(self):
        """Get list of selected images"""
        selected = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                image = self.table.item(row, 1).text()
                tag = self.table.item(row, 2).text()
                selected.append((image, tag))
        return selected
    
    def download_selected(self):
        """Download selected images with progress"""
        selected = self.get_selected_images()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select images to download")
            return
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        
        # Disable buttons during download
        self.set_buttons_enabled(False)
        
        # Start download worker
        self.download_worker = DownloadWorker(selected, self.config)
        self.download_worker.progress.connect(self.on_download_progress)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.start()
    
    def on_download_progress(self, percent, message):
        """Handle download progress updates"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)
    
    def on_download_finished(self, success, message):
        """Handle download completion"""
        self.progress_bar.setVisible(False)
        self.set_buttons_enabled(True)
        self.status_label.setText(message)
        self.refresh_all()
        
        if success:
            QMessageBox.information(self, "Download Complete", message)
    
    def load_to_docker(self):
        """Load selected images to Docker"""
        selected = self.get_selected_images()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select images to load")
            return
        
        storage = self.config.get('Local', 'storage_path')
        loaded = 0
        
        for image, tag in selected:
            tar_file = os.path.join(storage, f"{image}_{tag}.tar")
            if os.path.exists(tar_file):
                self.status_label.setText(f"Loading {image}:{tag}...")
                QApplication.processEvents()
                
                load_cmd = f'docker load -i "{tar_file}"'
                result = subprocess.run(load_cmd, shell=True, capture_output=True)
                
                if result.returncode == 0:
                    loaded += 1
        
        self.refresh_all()
        QMessageBox.information(self, "Complete", f"Loaded {loaded} images to Docker")
    
    def quick_run(self):
        """Quick run selected image with default settings"""
        selected = self.get_selected_images()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select an image to run")
            return
        
        if len(selected) > 1:
            QMessageBox.warning(self, "Multiple Selection", "Please select only one image for Quick Run")
            return
        
        image, tag = selected[0]
        
        # Show quick run dialog
        dialog = QuickRunDialog(self, image, tag, self.config)
        if dialog.exec_():
            port_mapping = dialog.port_input.text()
            container_name = dialog.name_input.text()
            
            registry = self.config.get('Artifactory', 'registry')
            repository = self.config.get('Artifactory', 'repository')
            full_name = f"{registry}/{repository}/{image}:{tag}"
            
            # Run container
            run_cmd = f'docker run -d -p {port_mapping} --name {container_name} {full_name}'
            result = subprocess.run(run_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                QMessageBox.information(self, "Success", 
                    f"Container '{container_name}' started!\n\nAccess at: http://localhost:{port_mapping.split(':')[0]}")
            else:
                QMessageBox.warning(self, "Error", f"Failed to start container:\n{result.stderr}")
    
    def remove_from_docker(self):
        """Remove selected images from Docker"""
        selected = self.get_selected_images()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select images to remove")
            return
        
        reply = QMessageBox.question(self, "Confirm", 
                                    f"Remove {len(selected)} images from Docker?",
                                    QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            registry = self.config.get('Artifactory', 'registry')
            repository = self.config.get('Artifactory', 'repository')
            
            for image, tag in selected:
                full_name = f"{registry}/{repository}/{image}:{tag}"
                remove_cmd = f'docker rmi {full_name} --force'
                subprocess.run(remove_cmd, shell=True, capture_output=True)
            
            self.refresh_all()
            QMessageBox.information(self, "Complete", f"Removed {len(selected)} images")
    
    def delete_local(self):
        """Delete local tar files"""
        selected = self.get_selected_images()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select files to delete")
            return
        
        reply = QMessageBox.question(self, "Confirm", 
                                    f"Delete {len(selected)} local files?",
                                    QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            storage = self.config.get('Local', 'storage_path')
            deleted = 0
            
            for image, tag in selected:
                tar_file = os.path.join(storage, f"{image}_{tag}.tar")
                if os.path.exists(tar_file):
                    os.remove(tar_file)
                    deleted += 1
            
            self.refresh_all()
            QMessageBox.information(self, "Complete", f"Deleted {deleted} files")
    
    def inspect_image(self, image, tag):
        """Show image details"""
        registry = self.config.get('Artifactory', 'registry')
        repository = self.config.get('Artifactory', 'repository')
        full_name = f"{registry}/{repository}/{image}:{tag}"
        
        # Get image info
        inspect_cmd = f'docker inspect {full_name}'
        result = subprocess.run(inspect_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Show in dialog
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Image Details: {image}:{tag}")
            dialog.setGeometry(200, 200, 800, 600)
            
            layout = QVBoxLayout(dialog)
            
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            
            # Format JSON
            try:
                import json
                data = json.loads(result.stdout)
                formatted = json.dumps(data, indent=2)
                text_edit.setPlainText(formatted)
            except:
                text_edit.setPlainText(result.stdout)
            
            layout.addWidget(text_edit)
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.close)
            layout.addWidget(close_btn)
            
            dialog.exec_()
        else:
            QMessageBox.warning(self, "Not Available", 
                               "Image must be loaded in Docker to inspect.\nPlease load the image first.")
    
    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self, self.config)
        if dialog.exec_():
            # Reload configuration
            self.config.load_config()
            self.apply_theme()
            self.setup_auto_refresh()
            self.refresh_all()
    
    def set_buttons_enabled(self, enabled):
        """Enable/disable buttons"""
        self.download_btn.setEnabled(enabled)
        self.load_btn.setEnabled(enabled)
        self.remove_btn.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)
        self.quick_run_btn.setEnabled(enabled)
    
    def closeEvent(self, event):
        """Save window size on close"""
        self.config.set('UI', 'window_width', str(self.width()))
        self.config.set('UI', 'window_height', str(self.height()))
        event.accept()

# ============================================================================
# Settings Dialog
# ============================================================================

class SettingsDialog(QDialog):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Settings")
        self.setGeometry(300, 300, 500, 400)
        
        layout = QVBoxLayout(self)
        
        # Artifactory settings
        group1 = QGroupBox("Artifactory Settings")
        form1 = QFormLayout()
        
        self.registry_input = QLineEdit(self.config.get('Artifactory', 'registry'))
        self.repository_input = QLineEdit(self.config.get('Artifactory', 'repository'))
        self.username_input = QLineEdit(self.config.get('Artifactory', 'username'))
        self.password_input = QLineEdit(self.config.get('Artifactory', 'password'))
        self.password_input.setEchoMode(QLineEdit.Password)
        
        form1.addRow("Registry:", self.registry_input)
        form1.addRow("Repository:", self.repository_input)
        form1.addRow("Username:", self.username_input)
        form1.addRow("Password/API Key:", self.password_input)
        
        group1.setLayout(form1)
        layout.addWidget(group1)
        
        # Local settings
        group2 = QGroupBox("Local Settings")
        form2 = QFormLayout()
        
        self.storage_input = QLineEdit(self.config.get('Local', 'storage_path'))
        self.refresh_input = QSpinBox()
        self.refresh_input.setRange(0, 3600)
        self.refresh_input.setValue(int(self.config.get('Local', 'auto_refresh_interval', fallback='300')))
        self.refresh_input.setSuffix(" seconds (0 = disabled)")
        
        form2.addRow("Storage Path:", self.storage_input)
        form2.addRow("Auto-refresh:", self.refresh_input)
        
        group2.setLayout(form2)
        layout.addWidget(group2)
        
        # UI settings
        group3 = QGroupBox("UI Settings")
        form3 = QFormLayout()
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["light", "dark"])
        self.theme_combo.setCurrentText(self.config.get('UI', 'theme', fallback='light'))
        
        form3.addRow("Theme:", self.theme_combo)
        
        group3.setLayout(form3)
        layout.addWidget(group3)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self.test_connection)
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(test_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def test_connection(self):
        """Test Artifactory connection"""
        try:
            url = f"https://{self.registry_input.text()}/artifactory/api/docker/{self.repository_input.text()}/v2/_catalog"
            response = requests.get(
                url,
                auth=(self.username_input.text(), self.password_input.text()),
                timeout=5
            )
            
            if response.status_code == 200:
                QMessageBox.information(self, "Success", "Connection successful!")
            else:
                QMessageBox.warning(self, "Failed", f"Connection failed: {response.status_code}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection error:\n{str(e)}")
    
    def save_settings(self):
        """Save settings to config"""
        self.config.set('Artifactory', 'registry', self.registry_input.text())
        self.config.set('Artifactory', 'repository', self.repository_input.text())
        self.config.set('Artifactory', 'username', self.username_input.text())
        self.config.set('Artifactory', 'password', self.password_input.text())
        self.config.set('Local', 'storage_path', self.storage_input.text())
        self.config.set('Local', 'auto_refresh_interval', str(self.refresh_input.value()))
        self.config.set('UI', 'theme', self.theme_combo.currentText())
        
        self.accept()

# ============================================================================
# Quick Run Dialog
# ============================================================================

class QuickRunDialog(QDialog):
    def __init__(self, parent, image, tag, config):
        super().__init__(parent)
        self.image = image
        self.tag = tag
        self.config = config
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle(f"Quick Run: {self.image}:{self.tag}")
        self.setGeometry(400, 400, 400, 200)
        
        layout = QFormLayout(self)
        
        # Container name
        self.name_input = QLineEdit(f"{self.image}-{self.tag}".replace(":", "-"))
        layout.addRow("Container Name:", self.name_input)
        
        # Port mapping
        self.port_input = QLineEdit("8080:5000")
        layout.addRow("Port Mapping:", self.port_input)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        run_btn = QPushButton("Run")
        run_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(run_btn)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow(btn_layout)

# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = EnhancedDockerManager()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
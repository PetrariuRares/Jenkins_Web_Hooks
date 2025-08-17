#!/usr/bin/env python3
"""
Docker Manager Application Test
A comprehensive PyQt5 application for managing Docker containers with JFrog Artifactory integration
"""

import sys
import os
import json
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
from requests.auth import HTTPBasicAuth

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QLabel, QLineEdit, QTextEdit, QComboBox, QSpinBox,
    QFileDialog, QMessageBox, QHeaderView, QGroupBox,
    QCheckBox, QProgressBar, QSplitter, QDialog,
    QDialogButtonBox, QFormLayout, QSlider, QMenu,
    QAction, QToolBar, QStatusBar, QSystemTrayIcon
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSettings,
    QSize, QProcess, QByteArray
)
from PyQt5.QtGui import (
    QIcon, QFont, QPalette, QColor, QPixmap,
    QPainter, QBrush, QPen
)

# Check if docker module is available
try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    print("Warning: Docker Python SDK not installed. Install with: pip install docker")


class DockerWorker(QThread):
    """Worker thread for Docker operations"""
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal(bool)
    update_progress = pyqtSignal(int)
    
    def __init__(self, operation, **kwargs):
        super().__init__()
        self.operation = operation
        self.kwargs = kwargs
        self.client = None
        
    def run(self):
        """Execute Docker operation in background"""
        try:
            if DOCKER_AVAILABLE:
                self.client = docker.from_env()
                
                if self.operation == "pull":
                    self.pull_image()
                elif self.operation == "remove":
                    self.remove_image()
                elif self.operation == "run":
                    self.run_container()
                elif self.operation == "stop":
                    self.stop_container()
                elif self.operation == "list_local":
                    self.list_local_images()
                    
                self.finished.emit(True)
            else:
                self.error.emit("Docker Python SDK not installed")
                self.finished.emit(False)
                
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)
            
    def pull_image(self):
        """Pull Docker image"""
        image_name = self.kwargs.get('image_name')
        self.progress.emit(f"Pulling {image_name}...")
        
        try:
            # Pull with progress tracking
            image = self.client.images.pull(image_name)
            self.progress.emit(f"Successfully pulled {image_name}")
        except Exception as e:
            raise Exception(f"Failed to pull {image_name}: {str(e)}")
            
    def remove_image(self):
        """Remove Docker image"""
        image_name = self.kwargs.get('image_name')
        self.progress.emit(f"Removing {image_name}...")
        
        try:
            self.client.images.remove(image_name, force=True)
            self.progress.emit(f"Successfully removed {image_name}")
        except Exception as e:
            raise Exception(f"Failed to remove {image_name}: {str(e)}")
            
    def run_container(self):
        """Run Docker container"""
        image_name = self.kwargs.get('image_name')
        cpu_limit = self.kwargs.get('cpu_limit', None)
        mem_limit = self.kwargs.get('mem_limit', None)
        
        self.progress.emit(f"Starting container from {image_name}...")
        
        try:
            container = self.client.containers.run(
                image_name,
                detach=True,
                cpu_count=cpu_limit,
                mem_limit=mem_limit,
                remove=False
            )
            self.progress.emit(f"Container {container.short_id} started")
        except Exception as e:
            raise Exception(f"Failed to run container: {str(e)}")
            
    def stop_container(self):
        """Stop Docker container"""
        container_id = self.kwargs.get('container_id')
        self.progress.emit(f"Stopping container {container_id}...")
        
        try:
            container = self.client.containers.get(container_id)
            container.stop()
            self.progress.emit(f"Container {container_id} stopped")
        except Exception as e:
            raise Exception(f"Failed to stop container: {str(e)}")


class TerminalDialog(QDialog):
    """Terminal dialog for executing Docker containers"""
    
    def __init__(self, image_name, parent=None):
        super().__init__(parent)
        self.image_name = image_name
        self.process = QProcess()
        self.init_ui()
        
    def init_ui(self):
        """Initialize terminal UI"""
        self.setWindowTitle(f"Terminal - {self.image_name}")
        self.setGeometry(100, 100, 800, 600)
        
        layout = QVBoxLayout()
        
        # Terminal output
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10pt;
            }
        """)
        layout.addWidget(self.terminal_output)
        
        # Command input
        input_layout = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter command...")
        self.command_input.returnPressed.connect(self.execute_command)
        input_layout.addWidget(self.command_input)
        
        self.execute_btn = QPushButton("Execute")
        self.execute_btn.clicked.connect(self.execute_command)
        input_layout.addWidget(self.execute_btn)
        
        layout.addLayout(input_layout)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.run_btn = QPushButton("Run Container")
        self.run_btn.clicked.connect(self.run_container)
        button_layout.addWidget(self.run_btn)
        
        self.stop_btn = QPushButton("Stop Container")
        self.stop_btn.clicked.connect(self.stop_container)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.terminal_output.clear)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Connect process signals
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)
        
    def run_container(self):
        """Run Docker container interactively"""
        self.terminal_output.append(f"Starting container from {self.image_name}...\n")
        
        # Docker run command with interactive mode
        cmd = f"docker run -it --rm {self.image_name}"
        
        self.process.start("cmd.exe", ["/c", cmd])
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
    def stop_container(self):
        """Stop running container"""
        if self.process.state() == QProcess.Running:
            self.process.terminate()
            self.terminal_output.append("\nContainer stopped.\n")
            
    def execute_command(self):
        """Execute command in container"""
        command = self.command_input.text()
        if command and self.process.state() == QProcess.Running:
            self.process.write(command.encode() + b'\n')
            self.command_input.clear()
            self.terminal_output.append(f"> {command}\n")
            
    def handle_stdout(self):
        """Handle standard output"""
        data = self.process.readAllStandardOutput()
        output = bytes(data).decode('utf-8', errors='ignore')
        self.terminal_output.append(output)
        
    def handle_stderr(self):
        """Handle standard error"""
        data = self.process.readAllStandardError()
        output = bytes(data).decode('utf-8', errors='ignore')
        self.terminal_output.append(f"Error: {output}")
        
    def process_finished(self):
        """Handle process finished"""
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.terminal_output.append("\nProcess finished.\n")


class DockerManagerApp(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings("DockerManager", "Settings")
        self.artifactory_images = []
        self.local_images = []
        self.containers = []
        self.docker_client = None
        self.init_docker_client()
        self.init_ui()
        self.load_settings()
        
    def init_docker_client(self):
        """Initialize Docker client"""
        if DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
            except Exception as e:
                QMessageBox.warning(self, "Docker Error", 
                                   f"Failed to connect to Docker: {str(e)}\n"
                                   "Make sure Docker Desktop is running.")
                
    def init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle("Docker Manager - Artifactory Integration")
        self.setGeometry(100, 100, 1400, 800)
        
        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background-color: white;
            }
            QTabBar::tab {
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #0078d4;
            }
            QPushButton {
                padding: 6px 12px;
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QTableWidget {
                gridline-color: #e0e0e0;
                selection-background-color: #e3f2fd;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create toolbar
        self.create_toolbar()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        # Create tab widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Create tabs
        self.create_artifactory_tab()
        self.create_local_images_tab()
        self.create_containers_tab()
        self.create_settings_tab()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds
        
    def create_toolbar(self):
        """Create application toolbar"""
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        
        # Refresh action
        refresh_action = QAction("🔄 Refresh All", self)
        refresh_action.triggered.connect(self.refresh_all)
        toolbar.addAction(refresh_action)
        
        toolbar.addSeparator()
        
        # Connection status
        self.connection_label = QLabel(" Status: Disconnected ")
        self.connection_label.setStyleSheet("""
            QLabel {
                background-color: #ffcccc;
                padding: 4px;
                border-radius: 3px;
            }
        """)
        toolbar.addWidget(self.connection_label)
        
    def create_artifactory_tab(self):
        """Create Artifactory images tab"""
        artifactory_widget = QWidget()
        layout = QVBoxLayout(artifactory_widget)
        
        # Connection group
        conn_group = QGroupBox("Artifactory Connection")
        conn_layout = QHBoxLayout()
        
        conn_layout.addWidget(QLabel("URL:"))
        self.artifactory_url = QLineEdit()
        self.artifactory_url.setPlaceholderText("https://your-artifactory.jfrog.io")
        conn_layout.addWidget(self.artifactory_url)
        
        conn_layout.addWidget(QLabel("Username:"))
        self.artifactory_user = QLineEdit()
        conn_layout.addWidget(self.artifactory_user)
        
        conn_layout.addWidget(QLabel("Password:"))
        self.artifactory_pass = QLineEdit()
        self.artifactory_pass.setEchoMode(QLineEdit.Password)
        conn_layout.addWidget(self.artifactory_pass)
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_artifactory)
        conn_layout.addWidget(self.connect_btn)
        
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)
        
        # Repository selection
        repo_layout = QHBoxLayout()
        repo_layout.addWidget(QLabel("Repository:"))
        self.repo_combo = QComboBox()
        self.repo_combo.setMinimumWidth(200)
        repo_layout.addWidget(self.repo_combo)
        
        self.fetch_images_btn = QPushButton("Fetch Images")
        self.fetch_images_btn.clicked.connect(self.fetch_artifactory_images)
        repo_layout.addWidget(self.fetch_images_btn)
        
        repo_layout.addStretch()
        layout.addLayout(repo_layout)
        
        # Images table
        self.artifactory_table = QTableWidget()
        self.artifactory_table.setColumnCount(6)
        self.artifactory_table.setHorizontalHeaderLabels([
            "Image Name", "Tag", "Size", "Created", "Actions", "Terminal"
        ])
        self.artifactory_table.horizontalHeader().setStretchLastSection(False)
        self.artifactory_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.artifactory_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.artifactory_table)
        
        # Bulk actions
        bulk_layout = QHBoxLayout()
        self.download_selected_btn = QPushButton("Download Selected")
        self.download_selected_btn.clicked.connect(self.download_selected_images)
        bulk_layout.addWidget(self.download_selected_btn)
        
        bulk_layout.addStretch()
        layout.addLayout(bulk_layout)
        
        self.tabs.addTab(artifactory_widget, "📦 Artifactory Images")
        
    def create_local_images_tab(self):
        """Create local Docker images tab"""
        local_widget = QWidget()
        layout = QVBoxLayout(local_widget)
        
        # Refresh button
        refresh_layout = QHBoxLayout()
        self.refresh_local_btn = QPushButton("Refresh Local Images")
        self.refresh_local_btn.clicked.connect(self.refresh_local_images)
        refresh_layout.addWidget(self.refresh_local_btn)
        
        # Search box
        self.search_local = QLineEdit()
        self.search_local.setPlaceholderText("Search images...")
        self.search_local.textChanged.connect(self.filter_local_images)
        refresh_layout.addWidget(self.search_local)
        
        refresh_layout.addStretch()
        layout.addLayout(refresh_layout)
        
        # Local images table
        self.local_table = QTableWidget()
        self.local_table.setColumnCount(7)
        self.local_table.setHorizontalHeaderLabels([
            "Repository", "Tag", "Image ID", "Size", "Created", "Actions", "Terminal"
        ])
        self.local_table.horizontalHeader().setStretchLastSection(False)
        self.local_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.local_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.local_table)
        
        # Bulk actions
        bulk_layout = QHBoxLayout()
        self.delete_selected_btn = QPushButton("Delete Selected")
        self.delete_selected_btn.clicked.connect(self.delete_selected_images)
        self.delete_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        bulk_layout.addWidget(self.delete_selected_btn)
        
        self.prune_btn = QPushButton("Prune Unused")
        self.prune_btn.clicked.connect(self.prune_images)
        bulk_layout.addWidget(self.prune_btn)
        
        bulk_layout.addStretch()
        layout.addLayout(bulk_layout)
        
        self.tabs.addTab(local_widget, "🖥️ Local Images")
        
    def create_containers_tab(self):
        """Create running containers tab"""
        containers_widget = QWidget()
        layout = QVBoxLayout(containers_widget)
        
        # Refresh and controls
        control_layout = QHBoxLayout()
        self.refresh_containers_btn = QPushButton("Refresh Containers")
        self.refresh_containers_btn.clicked.connect(self.refresh_containers)
        control_layout.addWidget(self.refresh_containers_btn)
        
        self.show_all_checkbox = QCheckBox("Show All (including stopped)")
        self.show_all_checkbox.stateChanged.connect(self.refresh_containers)
        control_layout.addWidget(self.show_all_checkbox)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # Containers table
        self.containers_table = QTableWidget()
        self.containers_table.setColumnCount(7)
        self.containers_table.setHorizontalHeaderLabels([
            "Container ID", "Image", "Name", "Status", "Ports", "Created", "Actions"
        ])
        self.containers_table.horizontalHeader().setStretchLastSection(False)
        self.containers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.containers_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.containers_table)
        
        # Container logs
        logs_group = QGroupBox("Container Logs")
        logs_layout = QVBoxLayout()
        
        self.logs_output = QTextEdit()
        self.logs_output.setMaximumHeight(200)
        self.logs_output.setReadOnly(True)
        self.logs_output.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                font-family: monospace;
            }
        """)
        logs_layout.addWidget(self.logs_output)
        
        logs_group.setLayout(logs_layout)
        layout.addWidget(logs_group)
        
        self.tabs.addTab(containers_widget, "▶️ Containers")
        
    def create_settings_tab(self):
        """Create settings tab"""
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)
        
        # Download settings
        download_group = QGroupBox("Download Settings")
        download_layout = QFormLayout()
        
        # Download location
        location_layout = QHBoxLayout()
        self.download_location = QLineEdit()
        self.download_location.setText(str(Path.home() / "DockerImages"))
        location_layout.addWidget(self.download_location)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_download_location)
        location_layout.addWidget(browse_btn)
        
        download_layout.addRow("Download Location:", location_layout)
        download_group.setLayout(download_layout)
        layout.addWidget(download_group)
        
        # Container runtime settings
        runtime_group = QGroupBox("Container Runtime Settings")
        runtime_layout = QFormLayout()
        
        # CPU limit
        cpu_layout = QHBoxLayout()
        self.cpu_limit = QSpinBox()
        self.cpu_limit.setMinimum(1)
        self.cpu_limit.setMaximum(32)
        self.cpu_limit.setValue(2)
        cpu_layout.addWidget(self.cpu_limit)
        cpu_layout.addWidget(QLabel("cores"))
        cpu_layout.addStretch()
        
        runtime_layout.addRow("CPU Limit:", cpu_layout)
        
        # Memory limit
        mem_layout = QHBoxLayout()
        self.memory_limit = QSpinBox()
        self.memory_limit.setMinimum(256)
        self.memory_limit.setMaximum(32768)
        self.memory_limit.setSingleStep(256)
        self.memory_limit.setValue(2048)
        mem_layout.addWidget(self.memory_limit)
        mem_layout.addWidget(QLabel("MB"))
        mem_layout.addStretch()
        
        runtime_layout.addRow("Memory Limit:", mem_layout)
        
        # Auto-remove containers
        self.auto_remove = QCheckBox("Auto-remove containers after stop")
        runtime_layout.addRow("", self.auto_remove)
        
        runtime_group.setLayout(runtime_layout)
        layout.addWidget(runtime_group)
        
        # Network settings
        network_group = QGroupBox("Network Settings")
        network_layout = QFormLayout()
        
        self.network_mode = QComboBox()
        self.network_mode.addItems(["bridge", "host", "none", "custom"])
        network_layout.addRow("Network Mode:", self.network_mode)
        
        network_group.setLayout(network_layout)
        layout.addWidget(network_group)
        
        # Auto-refresh settings
        refresh_group = QGroupBox("Auto-Refresh")
        refresh_layout = QFormLayout()
        
        self.auto_refresh_enabled = QCheckBox("Enable auto-refresh")
        self.auto_refresh_enabled.setChecked(True)
        refresh_layout.addRow("", self.auto_refresh_enabled)
        
        interval_layout = QHBoxLayout()
        self.refresh_interval = QSpinBox()
        self.refresh_interval.setMinimum(10)
        self.refresh_interval.setMaximum(300)
        self.refresh_interval.setValue(30)
        self.refresh_interval.valueChanged.connect(self.update_refresh_interval)
        interval_layout.addWidget(self.refresh_interval)
        interval_layout.addWidget(QLabel("seconds"))
        interval_layout.addStretch()
        
        refresh_layout.addRow("Refresh Interval:", interval_layout)
        refresh_group.setLayout(refresh_layout)
        layout.addWidget(refresh_group)
        
        # Save button
        save_layout = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        save_layout.addWidget(save_btn)
        save_layout.addStretch()
        layout.addLayout(save_layout)
        
        layout.addStretch()
        
        self.tabs.addTab(settings_widget, "⚙️ Settings")
        
    def connect_artifactory(self):
        """Connect to Artifactory"""
        url = self.artifactory_url.text().strip()
        username = self.artifactory_user.text().strip()
        password = self.artifactory_pass.text()
        
        if not all([url, username, password]):
            QMessageBox.warning(self, "Error", "Please fill in all connection fields")
            return
            
        try:
            # Test connection by fetching repositories
            api_url = f"{url}/artifactory/api/repositories"
            response = requests.get(
                api_url,
                auth=HTTPBasicAuth(username, password),
                timeout=10
            )
            
            if response.status_code == 200:
                repos = response.json()
                docker_repos = [r['key'] for r in repos if r.get('packageType') == 'docker']
                
                self.repo_combo.clear()
                self.repo_combo.addItems(docker_repos)
                
                self.connection_label.setText(" Status: Connected ")
                self.connection_label.setStyleSheet("""
                    QLabel {
                        background-color: #ccffcc;
                        padding: 4px;
                        border-radius: 3px;
                    }
                """)
                
                self.status_bar.showMessage(f"Connected to {url}")
                QMessageBox.information(self, "Success", "Connected to Artifactory!")
                
                # Save credentials for session
                self.save_settings()
                
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", f"Failed to connect: {str(e)}")
            self.connection_label.setText(" Status: Disconnected ")
            self.connection_label.setStyleSheet("""
                QLabel {
                    background-color: #ffcccc;
                    padding: 4px;
                    border-radius: 3px;
                }
            """)
            
    def fetch_artifactory_images(self):
        """Fetch images from selected Artifactory repository"""
        if not self.repo_combo.currentText():
            QMessageBox.warning(self, "Error", "Please select a repository")
            return
            
        url = self.artifactory_url.text().strip()
        username = self.artifactory_user.text().strip()
        password = self.artifactory_pass.text()
        repo = self.repo_combo.currentText()
        
        try:
            # Fetch images from repository
            api_url = f"{url}/artifactory/api/docker/{repo}/v2/_catalog"
            response = requests.get(
                api_url,
                auth=HTTPBasicAuth(username, password),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                repositories = data.get('repositories', [])
                
                self.artifactory_images = []
                self.artifactory_table.setRowCount(0)
                
                for image in repositories:
                    # Get tags for each image
                    tags_url = f"{url}/artifactory/api/docker/{repo}/v2/{image}/tags/list"
                    tags_response = requests.get(
                        tags_url,
                        auth=HTTPBasicAuth(username, password),
                        timeout=10
                    )
                    
                    if tags_response.status_code == 200:
                        tags_data = tags_response.json()
                        tags = tags_data.get('tags', ['latest'])
                        
                        for tag in tags:
                            full_image = f"{url.replace('https://', '').replace('http://', '')}/{repo}/{image}:{tag}"
                            self.artifactory_images.append({
                                'name': image,
                                'tag': tag,
                                'full_name': full_image,
                                'size': 'N/A',
                                'created': 'N/A'
                            })
                            
                self.populate_artifactory_table()
                self.status_bar.showMessage(f"Found {len(self.artifactory_images)} images")
                
            else:
                raise Exception(f"HTTP {response.status_code}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch images: {str(e)}")
            
    def populate_artifactory_table(self):
        """Populate Artifactory images table"""
        self.artifactory_table.setRowCount(len(self.artifactory_images))
        
        for row, image in enumerate(self.artifactory_images):
            # Image name
            self.artifactory_table.setItem(row, 0, QTableWidgetItem(image['name']))
            # Tag
            self.artifactory_table.setItem(row, 1, QTableWidgetItem(image['tag']))
            # Size
            self.artifactory_table.setItem(row, 2, QTableWidgetItem(image['size']))
            # Created
            self.artifactory_table.setItem(row, 3, QTableWidgetItem(image['created']))
            
            # Download button
            download_btn = QPushButton("Download")
            download_btn.clicked.connect(lambda checked, img=image: self.download_image(img))
            self.artifactory_table.setCellWidget(row, 4, download_btn)
            
            # Terminal button
            terminal_btn = QPushButton("🖥️")
            terminal_btn.clicked.connect(lambda checked, img=image: self.open_terminal(img['full_name']))
            self.artifactory_table.setCellWidget(row, 5, terminal_btn)
            
    def download_image(self, image):
        """Download Docker image"""
        reply = QMessageBox.question(
            self, "Download Image",
            f"Download {image['name']}:{image['tag']}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.worker = DockerWorker("pull", image_name=image['full_name'])
            self.worker.progress.connect(self.status_bar.showMessage)
            self.worker.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
            self.worker.finished.connect(self.refresh_local_images)
            self.worker.start()
            
    def download_selected_images(self):
        """Download selected images from Artifactory"""
        selected_rows = set()
        for item in self.artifactory_table.selectedItems():
            selected_rows.add(item.row())
            
        if not selected_rows:
            QMessageBox.warning(self, "Error", "Please select images to download")
            return
            
        images_to_download = [self.artifactory_images[row] for row in selected_rows]
        
        reply = QMessageBox.question(
            self, "Download Images",
            f"Download {len(images_to_download)} selected images?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for image in images_to_download:
                self.download_image(image)
                
    def refresh_local_images(self):
        """Refresh local Docker images"""
        if not DOCKER_AVAILABLE or not self.docker_client:
            QMessageBox.warning(self, "Error", "Docker is not available")
            return
            
        try:
            images = self.docker_client.images.list()
            self.local_images = []
            
            for image in images:
                tags = image.tags if image.tags else ['<none>']
                for tag in tags:
                    repo, tag_name = tag.split(':') if ':' in tag else (tag, 'latest')
                    self.local_images.append({
                        'repository': repo,
                        'tag': tag_name,
                        'id': image.short_id,
                        'size': f"{image.attrs['Size'] / 1024 / 1024:.2f} MB",
                        'created': image.attrs['Created'][:19],
                        'full_name': f"{repo}:{tag_name}"
                    })
                    
            self.populate_local_table()
            self.status_bar.showMessage(f"Found {len(self.local_images)} local images")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh local images: {str(e)}")
            
    def populate_local_table(self):
        """Populate local images table"""
        self.local_table.setRowCount(len(self.local_images))
        
        for row, image in enumerate(self.local_images):
            # Repository
            self.local_table.setItem(row, 0, QTableWidgetItem(image['repository']))
            # Tag
            self.local_table.setItem(row, 1, QTableWidgetItem(image['tag']))
            # Image ID
            self.local_table.setItem(row, 2, QTableWidgetItem(image['id']))
            # Size
            self.local_table.setItem(row, 3, QTableWidgetItem(image['size']))
            # Created
            self.local_table.setItem(row, 4, QTableWidgetItem(image['created']))
            
            # Action buttons
            action_layout = QHBoxLayout()
            action_widget = QWidget()
            
            run_btn = QPushButton("Run")
            run_btn.clicked.connect(lambda checked, img=image: self.run_image(img))
            action_layout.addWidget(run_btn)
            
            delete_btn = QPushButton("Delete")
            delete_btn.clicked.connect(lambda checked, img=image: self.delete_image(img))
            delete_btn.setStyleSheet("background-color: #dc3545;")
            action_layout.addWidget(delete_btn)
            
            action_widget.setLayout(action_layout)
            self.local_table.setCellWidget(row, 5, action_widget)
            
            # Terminal button
            terminal_btn = QPushButton("🖥️")
            terminal_btn.clicked.connect(lambda checked, img=image: self.open_terminal(img['full_name']))
            self.local_table.setCellWidget(row, 6, terminal_btn)
            
    def filter_local_images(self):
        """Filter local images based on search"""
        search_text = self.search_local.text().lower()
        for row in range(self.local_table.rowCount()):
            hide = True
            for col in range(3):  # Search in repo, tag, and ID
                item = self.local_table.item(row, col)
                if item and search_text in item.text().lower():
                    hide = False
                    break
            self.local_table.setRowHidden(row, hide)
            
    def run_image(self, image):
        """Run Docker image as container"""
        cpu = self.cpu_limit.value() if self.cpu_limit.value() > 0 else None
        memory = f"{self.memory_limit.value()}m" if self.memory_limit.value() > 0 else None
        
        self.worker = DockerWorker(
            "run",
            image_name=image['full_name'],
            cpu_limit=cpu,
            mem_limit=memory
        )
        self.worker.progress.connect(self.status_bar.showMessage)
        self.worker.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
        self.worker.finished.connect(self.refresh_containers)
        self.worker.start()
        
    def delete_image(self, image):
        """Delete local Docker image"""
        reply = QMessageBox.question(
            self, "Delete Image",
            f"Delete {image['repository']}:{image['tag']}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.worker = DockerWorker("remove", image_name=image['full_name'])
            self.worker.progress.connect(self.status_bar.showMessage)
            self.worker.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
            self.worker.finished.connect(self.refresh_local_images)
            self.worker.start()
            
    def delete_selected_images(self):
        """Delete selected local images"""
        selected_rows = set()
        for item in self.local_table.selectedItems():
            selected_rows.add(item.row())
            
        if not selected_rows:
            QMessageBox.warning(self, "Error", "Please select images to delete")
            return
            
        images_to_delete = [self.local_images[row] for row in selected_rows]
        
        reply = QMessageBox.question(
            self, "Delete Images",
            f"Delete {len(images_to_delete)} selected images?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for image in images_to_delete:
                self.delete_image(image)
                
    def prune_images(self):
        """Prune unused Docker images"""
        reply = QMessageBox.question(
            self, "Prune Images",
            "Remove all unused Docker images?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes and self.docker_client:
            try:
                self.docker_client.images.prune()
                self.refresh_local_images()
                QMessageBox.information(self, "Success", "Unused images pruned")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to prune images: {str(e)}")
                
    def refresh_containers(self):
        """Refresh running containers"""
        if not DOCKER_AVAILABLE or not self.docker_client:
            return
            
        try:
            show_all = self.show_all_checkbox.isChecked()
            containers = self.docker_client.containers.list(all=show_all)
            
            self.containers_table.setRowCount(len(containers))
            
            for row, container in enumerate(containers):
                # Container ID
                self.containers_table.setItem(row, 0, QTableWidgetItem(container.short_id))
                # Image
                self.containers_table.setItem(row, 1, QTableWidgetItem(container.image.tags[0] if container.image.tags else 'N/A'))
                # Name
                self.containers_table.setItem(row, 2, QTableWidgetItem(container.name))
                # Status
                self.containers_table.setItem(row, 3, QTableWidgetItem(container.status))
                # Ports
                ports = container.attrs.get('NetworkSettings', {}).get('Ports', {})
                port_str = ', '.join([f"{k}→{v[0]['HostPort']}" if v else k for k, v in ports.items()])
                self.containers_table.setItem(row, 4, QTableWidgetItem(port_str))
                # Created
                self.containers_table.setItem(row, 5, QTableWidgetItem(container.attrs['Created'][:19]))
                
                # Actions
                action_layout = QHBoxLayout()
                action_widget = QWidget()
                
                if container.status == 'running':
                    stop_btn = QPushButton("Stop")
                    stop_btn.clicked.connect(lambda checked, c=container: self.stop_container(c))
                    action_layout.addWidget(stop_btn)
                    
                    logs_btn = QPushButton("Logs")
                    logs_btn.clicked.connect(lambda checked, c=container: self.show_container_logs(c))
                    action_layout.addWidget(logs_btn)
                else:
                    start_btn = QPushButton("Start")
                    start_btn.clicked.connect(lambda checked, c=container: self.start_container(c))
                    action_layout.addWidget(start_btn)
                    
                    remove_btn = QPushButton("Remove")
                    remove_btn.clicked.connect(lambda checked, c=container: self.remove_container(c))
                    action_layout.addWidget(remove_btn)
                    
                action_widget.setLayout(action_layout)
                self.containers_table.setCellWidget(row, 6, action_widget)
                
            self.status_bar.showMessage(f"Found {len(containers)} containers")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh containers: {str(e)}")
            
    def stop_container(self, container):
        """Stop running container"""
        try:
            container.stop()
            self.refresh_containers()
            self.status_bar.showMessage(f"Stopped container {container.short_id}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop container: {str(e)}")
            
    def start_container(self, container):
        """Start stopped container"""
        try:
            container.start()
            self.refresh_containers()
            self.status_bar.showMessage(f"Started container {container.short_id}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start container: {str(e)}")
            
    def remove_container(self, container):
        """Remove container"""
        reply = QMessageBox.question(
            self, "Remove Container",
            f"Remove container {container.name}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                container.remove(force=True)
                self.refresh_containers()
                self.status_bar.showMessage(f"Removed container {container.short_id}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove container: {str(e)}")
                
    def show_container_logs(self, container):
        """Show container logs"""
        try:
            logs = container.logs(tail=100).decode('utf-8')
            self.logs_output.setText(logs)
        except Exception as e:
            self.logs_output.setText(f"Error fetching logs: {str(e)}")
            
    def open_terminal(self, image_name):
        """Open terminal for Docker image"""
        terminal = TerminalDialog(image_name, self)
        terminal.exec_()
        
    def browse_download_location(self):
        """Browse for download location"""
        folder = QFileDialog.getExistingDirectory(self, "Select Download Location")
        if folder:
            self.download_location.setText(folder)
            
    def update_refresh_interval(self):
        """Update auto-refresh interval"""
        if self.auto_refresh_enabled.isChecked():
            self.refresh_timer.setInterval(self.refresh_interval.value() * 1000)
            
    def auto_refresh(self):
        """Auto-refresh data"""
        if self.auto_refresh_enabled.isChecked():
            self.refresh_local_images()
            self.refresh_containers()
            
    def refresh_all(self):
        """Refresh all data"""
        self.refresh_local_images()
        self.refresh_containers()
        if self.repo_combo.currentText():
            self.fetch_artifactory_images()
            
    def save_settings(self):
        """Save application settings"""
        self.settings.setValue("artifactory_url", self.artifactory_url.text())
        self.settings.setValue("artifactory_user", self.artifactory_user.text())
        # Note: Password should be stored securely in production
        self.settings.setValue("download_location", self.download_location.text())
        self.settings.setValue("cpu_limit", self.cpu_limit.value())
        self.settings.setValue("memory_limit", self.memory_limit.value())
        self.settings.setValue("auto_remove", self.auto_remove.isChecked())
        self.settings.setValue("network_mode", self.network_mode.currentText())
        self.settings.setValue("auto_refresh", self.auto_refresh_enabled.isChecked())
        self.settings.setValue("refresh_interval", self.refresh_interval.value())
        
        QMessageBox.information(self, "Success", "Settings saved!")
        
    def load_settings(self):
        """Load application settings"""
        self.artifactory_url.setText(self.settings.value("artifactory_url", ""))
        self.artifactory_user.setText(self.settings.value("artifactory_user", ""))
        self.download_location.setText(self.settings.value("download_location", str(Path.home() / "DockerImages")))
        self.cpu_limit.setValue(int(self.settings.value("cpu_limit", 2)))
        self.memory_limit.setValue(int(self.settings.value("memory_limit", 2048)))
        self.auto_remove.setChecked(self.settings.value("auto_remove", False, type=bool))
        
        network = self.settings.value("network_mode", "bridge")
        index = self.network_mode.findText(network)
        if index >= 0:
            self.network_mode.setCurrentIndex(index)
            
        self.auto_refresh_enabled.setChecked(self.settings.value("auto_refresh", True, type=bool))
        self.refresh_interval.setValue(int(self.settings.value("refresh_interval", 30)))
        
        # Initial refresh
        self.refresh_local_images()
        self.refresh_containers()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Docker Manager")
    
    # Set application icon if available
    app.setWindowIcon(QIcon())
    
    # Create and show main window
    window = DockerManagerApp()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
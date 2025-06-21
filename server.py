import socket
import ssl
import json
import os
from pathlib import Path
from threading import Thread, Lock
import logging
import time
from google.cloud import storage
import os
from dotenv import load_dotenv

load_dotenv()

class FileTransferServer:
    def __init__(self, host='localhost', port=9999, storage_root='server_storage', certfile='server.crt', keyfile='server.key'):
        self.host = host
        self.port = port
        self.storage_root = Path(storage_root)
        self.certfile = certfile
        self.keyfile = keyfile
        self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.ssl_context.load_cert_chain(certfile=self.certfile, keyfile=self.keyfile)
        self.running = False

        if not self.storage_root.exists():
            self.storage_root.mkdir(parents=True)

        self.client_activities = {}  # Dictionary to track client activities
        self.client_activities_lock = Lock()  # Lock for thread-safe updates to client_activities
        self.client_sockets = []  # List to track client sockets
        self.client_sockets_lock = Lock()  # Lock for thread-safe updates to client_sockets
        self.logged_in_users = {}  # Set to track logged-in users
        self.logged_in_users_lock = Lock()  # Lock for thread-safe updates to logged_in_users
        logging.basicConfig(
            filename='server.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger()
        self.gcs_client = storage.Client.from_service_account_json(
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        )
        self.gcs_bucket_name = os.environ.get("GCS_BUCKET_NAME", "your-bucket-name")  
        self.gcs_bucket = self.gcs_client.bucket(self.gcs_bucket_name)

    def start(self):
        """Start the server"""
        raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket = self.ssl_context.wrap_socket(raw_socket, server_side=True)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True

        print(f"Server started with SSL on {self.host}:{self.port}")
        self.logger.info(f"Server started on {self.host}:{self.port}")

        Thread(target=self.monitor_client_activities, daemon=True).start()  # Start monitoring client activities

        try:
            while self.running:
                client_socket, addr = self.server_socket.accept()
                self.logger.info(f"Accepted connection from {addr}")
                with self.client_sockets_lock:
                    self.client_sockets.append(client_socket)  # Add client socket to list
                thread = Thread(target=self.handle_client, args=(client_socket, addr))
                thread.start()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            self.stop()
        finally:
            self.logger.info("Server stopped.")

    def stop(self):
        """Stop the server and close all client connections"""
        self.running = False
        with self.client_sockets_lock:
            for client_socket in self.client_sockets:
                try:
                    client_socket.close()
                except Exception as e:
                    self.logger.error(f"Error closing client socket: {e}")
        if self.server_socket:
            self.server_socket.close()

    def handle_client(self, client_socket, addr):
        """Handle client requests"""
        try:
            with self.client_activities_lock:
                self.client_activities[addr] = "Connected, authenticating..."
            self.logger.info(f"Client {addr} connected")

            # Receive authentication data
            auth_data = self._receive_data(client_socket)
            username = auth_data.get('username')
            password = auth_data.get('password')
            
            if not self.authenticate(username, password):
                self.logger.warning(f"Authentication failed for {addr}")
                self._send_data(client_socket, {'status': 'failed', 'message': 'Authentication failed'})
                client_socket.close()
                return
            with self.logged_in_users_lock:
                if username in self.logged_in_users:
                    self.logger.warning(f"User {username} is already logged in from {self.logged_in_users[username]}")
                    self._send_data(client_socket, {'status': 'failed', 'message': 'User already logged in'})
                    client_socket.close()
                    return
    
                # Add user to logged_in_users
                self.logged_in_users[username] = addr
            self.logger.info(f"Client {username} authenticated from {addr}")
            self._send_data(client_socket, {'status': 'success'})

            while self.running:
                request = self._receive_data(client_socket)
                if not request:
                    break
                
                command = request.get('command')
                filename = request.get('filename', '')
                with self.client_activities_lock:
                    self.client_activities[addr] = f"Executing command: {command} for file: {filename}"
                self.logger.info(f"{addr}: Executing command '{command}' on file '{filename}'")

                if command == 'list':
                    self.handle_list(client_socket, username)
                elif command == 'upload':
                    self.handle_upload(client_socket, username, filename, request.get('size'))
                elif command == 'download':
                    self.handle_download(client_socket, username, filename)
                elif command == 'view':
                    self.handle_view(client_socket, username, filename)
                elif command == 'delete':
                    self.handle_delete(client_socket, username, filename)
                else:
                    self._send_data(client_socket, {'status': 'failed', 'message': 'Invalid command'})
        except (socket.error, json.JSONDecodeError) as e:
            self.logger.error(f"Error handling client {addr}: {e}")
        finally:
            # Get username before removing from activities
            username = None
            for addr_key, activity in self.client_activities.items():
                if addr_key == addr:
                    # Try to extract username from activity logging
                    for user, address in self.logged_in_users.items():
                        if address == addr:
                            username = user
                            break
            with self.client_activities_lock:
                self.client_activities.pop(addr, None)
            with self.client_sockets_lock:
                if client_socket in self.client_sockets:
                    self.client_sockets.remove(client_socket)
            if username:
                with self.logged_in_users_lock:
                    if username in self.logged_in_users:
                        self.logged_in_users.pop(username)
                        self.logger.info(f"User {username} logged out")
            self.logger.info(f"Client {addr} disconnected")
            client_socket.close()

    def authenticate(self, username, password):
        """Authenticate user against id_passwd.txt file"""
        try:
            with open('id_passwd.txt', 'r') as file:
                for line in file:
                    line = line.strip()
                    if line:
                        stored_user, stored_pass = line.split(':')
                        if stored_user == username and stored_pass == password:
                            return True
            return False
        except Exception as e:
            self.logger.error(f"Error during authentication: {e}")
            return False

    def handle_list(self, client_socket, username):
        """Handle list command"""
        # user_dir = self.storage_root / username
        # if not user_dir.exists():
        #     user_dir.mkdir()
        files = []
        for blob in self.gcs_client.list_blobs(self.gcs_bucket_name, prefix=f"{username}/"):
            files.append(blob.name.split("/")[-1])
        self._send_data(client_socket, {'status': 'success', 'files': files})
        # self._send_data(client_socket, {'status': 'success', 'files': files})

    def handle_upload(self, client_socket, username, filename, size):
        """Handle upload command"""
        if not size or size <= 0:
            self._send_data(client_socket, {'status': 'failed', 'message': 'Invalid file size'})
            return
        # user_dir = self.storage_root / username
        # if not user_dir.exists():
        #     user_dir.mkdir()
        # safe_filename = os.path.basename(filename)
        # file_path = user_dir / safe_filename

        blob = self.gcs_bucket.blob(f"{username}/{filename}")

        received = 0
        chunks = []
        while received < size:
            chunk = client_socket.recv(min(4096, size - received))
            if not chunk:
                break
            chunks.append(chunk)
            received += len(chunk)

        if received != size:
            self.logger.warning(f"Upload error: Expected {size} bytes but received {received} for file '{filename}'")
            self._send_data(client_socket, {'status': 'failed', 'message': 'Upload failed'})
        else:
            blob.upload_from_string(b''.join(chunks))
            self._send_data(client_socket, {'status': 'success'})
            self.logger.info(f"File '{filename}' uploaded by {username}")
     
    def handle_download(self, client_socket, username, filename):
        """Handle download command"""
        safe_filename = os.path.basename(filename)
        file_path = self.storage_root / username / safe_filename
        safe_filename = os.path.basename(filename)
        blob = self.gcs_bucket.blob(f"{username}/{filename}")

        if blob.exists():
            data = blob.download_as_bytes()
            self._send_data(client_socket, {'status': 'success', 'size': len(data)})
            client_socket.sendall(data)
        else:
            self._send_data(client_socket, {'status': 'failed', 'message': 'File not found'})

    def handle_view(self, client_socket, username, filename):
        """Handle view command"""
        # Sanitize filename to prevent path traversal
        safe_filename = os.path.basename(filename)
        blob = self.gcs_bucket.blob(f"{username}/{filename}")

        if blob.exists():
            try:
                data = blob.download_as_bytes()
                preview_data = data[:1024]
                try:
                    preview_text = preview_data.decode('utf-8')
                    is_text = True
                except UnicodeDecodeError:
                    preview_text = "[Binary file content - preview not available]"
                    is_text = False
                self._send_data(client_socket, {
                    'status': 'success',
                    'preview': preview_text,
                    'is_binary': not is_text
                })
            except Exception as e:
                self.logger.error(f"Error viewing file: {e}")
                self._send_data(client_socket, {'status': 'failed', 'message': 'Error reading file'})
        else:
            self._send_data(client_socket, {'status': 'failed', 'message': 'File not found'})
    def handle_delete(self, client_socket, username, filename):
        """Handle delete command"""
        safe_filename = os.path.basename(filename)
        blob = self.gcs_bucket.blob(f"{username}/{filename}")

        if blob.exists():
            try:
                blob.delete()
                self._send_data(client_socket, {'status': 'success'})
                self.logger.info(f"File '{safe_filename}' deleted by {username}")
            except Exception as e:
                self.logger.error(f"Error deleting file: {e}")
                self._send_data(client_socket, {'status': 'failed', 'message': f'Error: {str(e)}'})
        else:
            self._send_data(client_socket, {'status': 'failed', 'message': 'File not found'})

    def _send_data(self, client_socket, data):
        """Helper function to send JSON data to the client"""
        client_socket.send(json.dumps(data).encode())

    def _receive_data(self, client_socket):
        """Helper function to receive JSON data from the client"""
        try:
            data = client_socket.recv(4096)
            while data:
                try:
                    return json.loads(data.decode())
                except json.JSONDecodeError:
                    # Keep receiving data until we can parse valid JSON
                    chunk = client_socket.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            return None
        except socket.error as e:
            self.logger.error(f"Error receiving data: {e}")
            return None

    def show_client_activities(self):
        """Display current client activities"""
        with self.client_activities_lock:
            print("\nCurrent Client Activities:")
            for addr, activity in self.client_activities.items():
                print(f"{addr}: {activity}")

    def monitor_client_activities(self):
        """Monitor and display client activities periodically"""
        while self.running:
            self.show_client_activities()
            time.sleep(15)  # Adjust interval as needed

def main():
    server = FileTransferServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("Server stopping...")
        server.stop()

if __name__ == '__main__':
    main()

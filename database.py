import sqlite3
import hashlib
import os
from pathlib import Path
import logging

class UserDatabase:
    def __init__(self, db_path='users.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with users table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        # Create default admin user if no users exist
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            self.create_user('admin', 'admin123')
            self.create_user('testuser', 'test123')
            logging.info("Created default users: admin and testuser")
        
        conn.commit()
        conn.close()
    
    def _hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, username, password):
        """Create a new user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            password_hash = self._hash_password(password)
            cursor.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                (username, password_hash)
            )
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False  # User already exists
        except Exception as e:
            logging.error(f"Error creating user: {e}")
            return False
    
    def authenticate(self, username, password):
        """Authenticate user credentials"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            password_hash = self._hash_password(password)
            cursor.execute(
                'SELECT id FROM users WHERE username = ? AND password_hash = ?',
                (username, password_hash)
            )
            
            result = cursor.fetchone()
            
            if result:
                # Update last login
                cursor.execute(
                    'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = ?',
                    (username,)
                )
                conn.commit()
            
            conn.close()
            return result is not None
        except Exception as e:
            logging.error(f"Error during authentication: {e}")
            return False
    
    def list_users(self):
        """List all users (for admin purposes)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT username, created_at, last_login FROM users')
            users = cursor.fetchall()
            
            conn.close()
            return users
        except Exception as e:
            logging.error(f"Error listing users: {e}")
            return []
    
    def delete_user(self, username):
        """Delete a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM users WHERE username = ?', (username,))
            deleted = cursor.rowcount > 0
            
            conn.commit()
            conn.close()
            return deleted
        except Exception as e:
            logging.error(f"Error deleting user: {e}")
            return False
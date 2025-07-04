#!/usr/bin/env python3
"""
User Management CLI for the Distributed File System
"""
import argparse
from database import UserDatabase
from getpass import getpass

def main():
    parser = argparse.ArgumentParser(description='User Management for Distributed File System')
    parser.add_argument('action', choices=['create', 'list', 'delete'], 
                       help='Action to perform')
    parser.add_argument('--username', '-u', help='Username')
    
    args = parser.parse_args()
    db = UserDatabase()
    
    if args.action == 'create':
        if not args.username:
            username = input("Username: ")
        else:
            username = args.username
        
        password = getpass("Password: ")
        confirm_password = getpass("Confirm password: ")
        
        if password != confirm_password:
            print("Passwords don't match!")
            return
        
        if db.create_user(username, password):
            print(f"User '{username}' created successfully!")
        else:
            print(f"Failed to create user '{username}' (may already exist)")
    
    elif args.action == 'list':
        users = db.list_users()
        print("\nUsers in system:")
        print("-" * 60)
        for username, created_at, last_login in users:
            last_login_str = last_login if last_login else "Never"
            print(f"Username: {username}")
            print(f"Created: {created_at}")
            print(f"Last Login: {last_login_str}")
            print("-" * 60)
    
    elif args.action == 'delete':
        if not args.username:
            username = input("Username to delete: ")
        else:
            username = args.username
        
        confirm = input(f"Are you sure you want to delete user '{username}'? (y/N): ")
        if confirm.lower() == 'y':
            if db.delete_user(username):
                print(f"User '{username}' deleted successfully!")
            else:
                print(f"Failed to delete user '{username}' (may not exist)")
        else:
            print("Deletion cancelled.")

if __name__ == '__main__':
    main()
# Distributed File System

A secure SSL-enabled file transfer system with Google Cloud Storage backend.

## Features
- SSL/TLS encrypted connections
- User authentication
- File upload/download/view/delete operations
- Google Cloud Storage integration
- Multi-client support

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file with your GCS credentials:
```
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GCS_BUCKET_NAME=your-bucket-name
```

3. Generate SSL certificates:
```bash
make generate_certs
```

4. Set up user database:
```bash
# The database will be created automatically with default users
# To create additional users:
python user_manager.py create --username newuser

# To list users:
python user_manager.py list

# To delete users:
python user_manager.py delete --username olduser
```


5. Create GCS bucket:
```bash
python bucket.py
```

## Default Users
- Username: `admin`, Password: `admin123`
- Username: `testuser`, Password: `test123`

## User Management
Use `user_manager.py` to manage users:
- Create users: `python user_manager.py create`
- List users: `python user_manager.py list`
- Delete users: `python user_manager.py delete`

## Usage

Start server:
```bash
make run_server
```

Start client:
```bash
make run_client
```

## Security Note
This is a development project. Do not use in production without implementing proper password hashing and security measures.
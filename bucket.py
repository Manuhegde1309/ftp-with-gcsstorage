from google.cloud import storage
import os
from dotenv import load_dotenv
from google.api_core.exceptions import Conflict

# 1️⃣ Load .env
load_dotenv()

# 2️⃣ Get Bucket Name
bucket_name = os.environ["GCS_BUCKET_NAME"]

# 3️⃣ Authenticate Service Account
client = storage.Client.from_service_account_json(
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
)

# 4️⃣ Try to Create Bucket
try:
    bucket = client.create_bucket(bucket_name)  # Will create the bucket
    print(f"✅ Created new bucket: {bucket.name}")

except Conflict:
    # Conflict occurs if bucket already exists globally
    print(f"⚡️ Bucket {bucket_name} already exists.")

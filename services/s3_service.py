"""
Backblaze B2 S3-compatible storage service for V2.1.

Provides:
- Presigned URL generation for uploads and downloads
- File verification and retrieval
- Parameter storage (parameters.json)
- Output file management
"""

import boto3
import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from botocore.exceptions import ClientError


class S3Service:
    """Backblaze B2 S3-compatible storage service."""

    _instance = None

    def __new__(cls):
        """Singleton pattern for connection reuse."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize S3 client (only once due to singleton)."""
        if self._initialized:
            return
        self._initialize()
        self._initialized = True

    def _initialize(self):
        """Initialize S3 client with Backblaze B2 credentials."""
        self.client = boto3.client(
            "s3",
            endpoint_url=os.getenv("AWS_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION", "us-east-005"),
        )
        self.bucket = os.getenv("S3_BUCKET", "agensium-files")
        print(f"✓ S3Service initialized with bucket: {self.bucket}")

    # =========================================================================
    # UPLOAD URL GENERATION
    # =========================================================================

    def generate_upload_url(
        self,
        user_id: int,
        task_id: str,
        filename: str,
        content_type: str = "text/csv",
        expires_in: int = 900  # 15 minutes
    ) -> Dict[str, Any]:
        """
        Generate presigned URL for file upload.
        
        Args:
            user_id: User ID for path construction
            task_id: Task ID for path construction
            filename: Original filename
            content_type: MIME type of the file
            expires_in: URL expiration in seconds (default 15 min)
            
        Returns:
            Dict with url, key, method, headers, expires_at
        """
        key = f"users/{user_id}/tasks/{task_id}/inputs/{filename}"
        
        url = self.client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": content_type
            },
            ExpiresIn=expires_in
        )
        
        return {
            "url": url,
            "key": key,
            "method": "PUT",
            "headers": {"Content-Type": content_type},
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        }

    def generate_parameter_upload_url(
        self,
        user_id: int,
        task_id: str,
        expires_in: int = 900
    ) -> Dict[str, Any]:
        """
        Generate presigned URL for parameters.json upload.
        
        Args:
            user_id: User ID for path construction
            task_id: Task ID for path construction
            expires_in: URL expiration in seconds
            
        Returns:
            Dict with url, key, method, headers, expires_at
        """
        key = f"users/{user_id}/tasks/{task_id}/inputs/parameters.json"
        
        url = self.client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": "application/json"
            },
            ExpiresIn=expires_in
        )
        
        return {
            "url": url,
            "key": key,
            "method": "PUT",
            "headers": {"Content-Type": "application/json"},
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        }

    # =========================================================================
    # DOWNLOAD URL GENERATION
    # =========================================================================

    def generate_download_url(
        self,
        key: str,
        expires_in: int = 3600  # 1 hour
    ) -> str:
        """
        Generate presigned URL for file download.
        
        Args:
            key: S3 object key
            expires_in: URL expiration in seconds
            
        Returns:
            Presigned download URL
        """
        return self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in
        )

    # =========================================================================
    # FILE OPERATIONS
    # =========================================================================

    def file_exists(self, key: str) -> bool:
        """
        Check if file exists in bucket.
        
        Args:
            key: S3 object key
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise

    def get_file_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata.
        
        Args:
            key: S3 object key
            
        Returns:
            Dict with size_bytes, content_type, last_modified, or None if not found
        """
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=key)
            return {
                "size_bytes": response['ContentLength'],
                "content_type": response.get('ContentType'),
                "last_modified": response['LastModified']
            }
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            raise

    def get_file_bytes(self, key: str) -> bytes:
        """
        Download file content as bytes.
        
        Args:
            key: S3 object key
            
        Returns:
            File content as bytes
            
        Raises:
            ClientError: If file not found or access denied
        """
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response['Body'].read()

    def get_file_stream(self, key: str):
        """
        Get streaming body for file (useful for large files).
        
        Args:
            key: S3 object key
            
        Returns:
            StreamingBody object
        """
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response['Body']

    # =========================================================================
    # PARAMETER OPERATIONS
    # =========================================================================

    def get_parameters(self, user_id: int, task_id: str) -> Optional[Dict]:
        """
        Get parameters.json for a task.
        
        Args:
            user_id: User ID
            task_id: Task ID
            
        Returns:
            Parsed parameters dict, or None if not found
        """
        key = f"users/{user_id}/tasks/{task_id}/inputs/parameters.json"
        
        if not self.file_exists(key):
            return None

        content = self.get_file_bytes(key)
        return json.loads(content.decode('utf-8'))

    # =========================================================================
    # UPLOAD OPERATIONS
    # =========================================================================

    def upload_file(
        self,
        key: str,
        content: bytes,
        content_type: str = "text/csv"
    ) -> Dict[str, Any]:
        """
        Upload file content to S3.
        
        Args:
            key: S3 object key
            content: File content as bytes
            content_type: MIME type
            
        Returns:
            Dict with key and size_bytes
        """
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type
        )
        
        return {
            "key": key,
            "size_bytes": len(content)
        }

    def upload_json(
        self,
        key: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Upload JSON data to S3.
        
        Args:
            key: S3 object key
            data: Dictionary to serialize as JSON
            
        Returns:
            Dict with key and size_bytes
        """
        content = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        return self.upload_file(key, content, "application/json")

    # =========================================================================
    # LISTING OPERATIONS
    # =========================================================================

    def list_files(self, prefix: str) -> List[Dict[str, Any]]:
        """
        List files with given prefix.
        
        Args:
            prefix: S3 key prefix to search
            
        Returns:
            List of dicts with key, filename, size_bytes, last_modified
        """
        response = self.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=prefix
        )

        files = []
        for obj in response.get('Contents', []):
            filename = obj['Key'].replace(prefix, '').lstrip('/')
            if filename:
                files.append({
                    'key': obj['Key'],
                    'filename': filename,
                    'size_bytes': obj['Size'],
                    'last_modified': obj['LastModified']
                })
        return files

    def list_input_files(
        self,
        user_id: int,
        task_id: str
    ) -> List[Dict[str, Any]]:
        """
        List all files in task inputs folder.
        
        Args:
            user_id: User ID
            task_id: Task ID
            
        Returns:
            List of input files (excluding parameters.json)
        """
        prefix = f"users/{user_id}/tasks/{task_id}/inputs/"
        files = self.list_files(prefix)
        # Optionally filter out parameters.json
        return [f for f in files if f['filename'] != 'parameters.json']

    def list_output_files(
        self,
        user_id: int,
        task_id: str
    ) -> List[Dict[str, Any]]:
        """
        List all files in task outputs folder.
        
        Args:
            user_id: User ID
            task_id: Task ID
            
        Returns:
            List of output files
        """
        prefix = f"users/{user_id}/tasks/{task_id}/outputs/"
        return self.list_files(prefix)

    # =========================================================================
    # DELETE OPERATIONS
    # =========================================================================

    def delete_file(self, key: str) -> bool:
        """
        Delete a file from S3.
        
        Args:
            key: S3 object key
            
        Returns:
            True if deleted successfully
        """
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete_folder(self, prefix: str) -> int:
        """
        Delete all files with given prefix.
        
        Args:
            prefix: S3 key prefix to delete
            
        Returns:
            Number of files deleted
        """
        files = self.list_files(prefix)
        deleted_count = 0
        
        for file in files:
            if self.delete_file(file['key']):
                deleted_count += 1
                
        return deleted_count

    def delete_task_files(self, user_id: int, task_id: str) -> int:
        """
        Delete all files for a task (inputs and outputs).
        
        Args:
            user_id: User ID
            task_id: Task ID
            
        Returns:
            Number of files deleted
        """
        prefix = f"users/{user_id}/tasks/{task_id}/"
        return self.delete_folder(prefix)

    # =========================================================================
    # VERIFICATION
    # =========================================================================

    def verify_input_files(
        self,
        user_id: int,
        task_id: str,
        required_files: List[str]
    ) -> Dict[str, Any]:
        """
        Verify that required input files exist in S3.
        
        Args:
            user_id: User ID
            task_id: Task ID
            required_files: List of required file keys (e.g., ['primary'])
            
        Returns:
            Dict with:
                - verified: bool (all files found)
                - found: list of found file keys
                - missing: list of missing file keys
                - files: dict of file_key -> file_info
        """
        prefix = f"users/{user_id}/tasks/{task_id}/inputs/"
        existing_files = self.list_files(prefix)
        
        # Build a map of what we found
        found_map = {}
        for f in existing_files:
            filename = f['filename'].lower()
            # Map common patterns
            if 'primary' in filename or filename == existing_files[0]['filename'].lower():
                found_map['primary'] = f
            elif 'baseline' in filename:
                found_map['baseline'] = f
            elif filename != 'parameters.json':
                # First non-parameters file becomes primary if not set
                if 'primary' not in found_map:
                    found_map['primary'] = f
        
        # Check requirements
        found = []
        missing = []
        files_info = {}
        
        for file_key in required_files:
            if file_key in found_map:
                found.append(file_key)
                files_info[file_key] = {
                    "key": found_map[file_key]['key'],
                    "size_bytes": found_map[file_key]['size_bytes'],
                    "verified_at": datetime.now(timezone.utc).isoformat()
                }
            else:
                missing.append(file_key)
        
        return {
            "verified": len(missing) == 0,
            "found": found,
            "missing": missing,
            "files": files_info
        }

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def get_task_prefix(self, user_id: int, task_id: str) -> str:
        """Get S3 prefix for a task."""
        return f"users/{user_id}/tasks/{task_id}/"

    def get_input_prefix(self, user_id: int, task_id: str) -> str:
        """Get S3 prefix for task inputs."""
        return f"users/{user_id}/tasks/{task_id}/inputs/"

    def get_output_prefix(self, user_id: int, task_id: str) -> str:
        """Get S3 prefix for task outputs."""
        return f"users/{user_id}/tasks/{task_id}/outputs/"


# Singleton instance for easy import
s3_service = S3Service()

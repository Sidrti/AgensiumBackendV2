"""
Complete Backblaze B2 S3-Compatible Upload Testing Suite

This script tests all components of the B2 integration:
- Connection verification
- Presigned URL generation
- Upload functionality
- Download functionality
- Bucket verification
"""

import boto3
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from botocore.exceptions import ClientError

# Load environment variables
load_dotenv()

class B2TestSuite:
    def __init__(self):
        self.endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        self.access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region = os.getenv("AWS_REGION")
        self.bucket = os.getenv("S3_BUCKET")
        self.s3_client = None
        self.test_results = []
        
    def log_test(self, test_name, status, message=""):
        """Log test result"""
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        icon = "✅" if status == "PASS" else "❌"
        print(f"{icon} {test_name}: {status}")
        if message:
            print(f"   └─ {message}")
    
    def print_header(self, title):
        """Print section header"""
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}\n")
    
    def test_environment_variables(self):
        """Test 1: Verify all environment variables are set"""
        self.print_header("TEST 1: Environment Variables")
        
        required_vars = {
            "AWS_ENDPOINT_URL": self.endpoint_url,
            "AWS_ACCESS_KEY_ID": self.access_key,
            "AWS_SECRET_ACCESS_KEY": self.secret_key,
            "AWS_REGION": self.region,
            "S3_BUCKET": self.bucket
        }
        
        all_set = True
        for var_name, var_value in required_vars.items():
            if var_value:
                self.log_test(f"Environment: {var_name}", "PASS", var_value[:20] + "***" if len(str(var_value)) > 20 else var_value)
            else:
                self.log_test(f"Environment: {var_name}", "FAIL", "NOT SET")
                all_set = False
        
        return all_set
    
    def test_s3_client_initialization(self):
        """Test 2: Initialize S3 client"""
        self.print_header("TEST 2: S3 Client Initialization")
        
        try:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            )
            self.log_test("S3 Client Creation", "PASS", f"Client initialized for {self.endpoint_url}")
            return True
        except Exception as e:
            self.log_test("S3 Client Creation", "FAIL", str(e))
            return False
    
    def test_connection(self):
        """Test 3: Test connection to Backblaze B2"""
        self.print_header("TEST 3: Connection to Backblaze B2")
        
        if not self.s3_client:
            self.log_test("B2 Connection", "FAIL", "S3 client not initialized")
            return False
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                MaxKeys=1
            )
            self.log_test("B2 Connection", "PASS", f"Successfully connected to bucket '{self.bucket}'")
            self.log_test("Bucket Response", "PASS", f"Bucket contains {response.get('KeyCount', 0)} objects")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            self.log_test("B2 Connection", "FAIL", f"{error_code}: {error_msg}")
            return False
    
    def test_generate_presigned_upload_url(self):
        """Test 4: Generate presigned upload URL"""
        self.print_header("TEST 4: Generate Presigned Upload URL")
        
        if not self.s3_client:
            self.log_test("Presigned URL Generation", "FAIL", "S3 client not initialized")
            return None
        
        try:
            user_id = "test-user"
            task_id = "test-task-001"
            filename = "sample_test_data.csv"
            
            key = f"users/{user_id}/tasks/{task_id}/inputs/{filename}"
            
            presigned_url = self.s3_client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": key,
                    "ContentType": "text/csv"
                },
                ExpiresIn=900  # 15 minutes
            )
            
            self.log_test("Presigned URL Generation", "PASS", "URL generated successfully")
            self.log_test("Upload Key", "PASS", key)
            self.log_test("Expiration", "PASS", "900 seconds (15 minutes)")
            
            return {
                "url": presigned_url,
                "key": key,
                "user_id": user_id,
                "task_id": task_id,
                "filename": filename
            }
        except Exception as e:
            self.log_test("Presigned URL Generation", "FAIL", str(e))
            return None
    
    def test_upload_file(self, presigned_url_info):
        """Test 5: Upload file using presigned URL"""
        self.print_header("TEST 5: Upload File Using Presigned URL")
        
        if not presigned_url_info:
            self.log_test("File Upload", "FAIL", "No presigned URL info available")
            return False
        
        try:
            import requests
            
            # Get the sample CSV file
            script_dir = Path(__file__).parent
            csv_file = script_dir / "sample_test_data.csv"
            
            if not csv_file.exists():
                self.log_test("File Upload", "FAIL", f"Sample file not found: {csv_file}")
                return False
            
            with open(csv_file, 'rb') as f:
                files = {'file': f}
                headers = {'Content-Type': 'text/csv'}
                
                response = requests.put(
                    presigned_url_info['url'],
                    data=f.read(),
                    headers=headers
                )
            
            if response.status_code == 200:
                self.log_test("File Upload", "PASS", f"File uploaded successfully")
                self.log_test("Upload Location", "PASS", f"s3://{self.bucket}/{presigned_url_info['key']}")
                self.log_test("Response Code", "PASS", str(response.status_code))
                return presigned_url_info['key']
            else:
                self.log_test("File Upload", "FAIL", f"HTTP {response.status_code}: {response.text}")
                return False
                
        except ImportError:
            self.log_test("File Upload", "FAIL", "requests library not installed. Run: pip install requests")
            return False
        except Exception as e:
            self.log_test("File Upload", "FAIL", str(e))
            return False
    
    def test_verify_upload(self, s3_key):
        """Test 6: Verify file exists in bucket"""
        self.print_header("TEST 6: Verify File Upload")
        
        if not self.s3_client or not s3_key:
            self.log_test("File Verification", "FAIL", "No S3 key provided")
            return False
        
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket,
                Key=s3_key
            )
            
            file_size = response['ContentLength']
            last_modified = response['LastModified']
            
            self.log_test("File Verification", "PASS", f"File exists in bucket")
            self.log_test("File Size", "PASS", f"{file_size} bytes")
            self.log_test("Last Modified", "PASS", str(last_modified))
            
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                self.log_test("File Verification", "FAIL", "File not found in bucket")
            else:
                self.log_test("File Verification", "FAIL", str(e))
            return False
    
    def test_generate_presigned_download_url(self):
        """Test 7: Generate presigned download URL"""
        self.print_header("TEST 7: Generate Presigned Download URL")
        
        if not self.s3_client:
            self.log_test("Download URL Generation", "FAIL", "S3 client not initialized")
            return None
        
        try:
            user_id = "test-user"
            task_id = "test-task-001"
            filename = "output.csv"
            
            key = f"users/{user_id}/tasks/{task_id}/outputs/{filename}"
            
            presigned_url = self.s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": key
                },
                ExpiresIn=3600  # 1 hour
            )
            
            self.log_test("Download URL Generation", "PASS", "URL generated successfully")
            self.log_test("Download Key", "PASS", key)
            self.log_test("Expiration", "PASS", "3600 seconds (1 hour)")
            
            return presigned_url
        except Exception as e:
            self.log_test("Download URL Generation", "FAIL", str(e))
            return None
    
    def test_list_bucket_contents(self):
        """Test 8: List bucket contents"""
        self.print_header("TEST 8: List Bucket Contents")
        
        if not self.s3_client:
            self.log_test("Bucket Listing", "FAIL", "S3 client not initialized")
            return False
        
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket)
            
            if 'Contents' in response:
                objects = response['Contents']
                self.log_test("Bucket Listing", "PASS", f"Found {len(objects)} objects")
                
                # Show first 5 objects
                for i, obj in enumerate(objects[:5]):
                    self.log_test(f"Object {i+1}", "PASS", f"{obj['Key']} ({obj['Size']} bytes)")
                
                if len(objects) > 5:
                    self.log_test("...", "PASS", f"and {len(objects) - 5} more objects")
            else:
                self.log_test("Bucket Listing", "PASS", "Bucket is empty")
            
            return True
        except Exception as e:
            self.log_test("Bucket Listing", "FAIL", str(e))
            return False
    
    def generate_test_report(self):
        """Generate final test report"""
        self.print_header("TEST REPORT SUMMARY")
        
        passed = len([t for t in self.test_results if t['status'] == 'PASS'])
        failed = len([t for t in self.test_results if t['status'] == 'FAIL'])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Success Rate: {(passed/total)*100:.1f}%\n")
        
        if failed == 0:
            print("🎉 ALL TESTS PASSED! Your B2 integration is ready.")
        else:
            print("⚠️ Some tests failed. Please review the errors above.")
        
        # Save report to file
        report_file = Path(__file__).parent / "test_report.json"
        with open(report_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        print(f"\nDetailed report saved to: {report_file}")
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("\n" + "="*70)
        print("  BACKBLAZE B2 COMPLETE INTEGRATION TEST SUITE")
        print("="*70)
        
        # Test 1: Environment
        if not self.test_environment_variables():
            print("\n❌ Environment variables not set. Exiting.")
            return False
        
        # Test 2: Client initialization
        if not self.test_s3_client_initialization():
            print("\n❌ Failed to initialize S3 client. Exiting.")
            return False
        
        # Test 3: Connection
        if not self.test_connection():
            print("\n❌ Failed to connect to B2. Exiting.")
            return False
        
        # Test 4: Presigned URL
        presigned_url_info = self.test_generate_presigned_upload_url()
        if not presigned_url_info:
            print("\n❌ Failed to generate presigned URL. Exiting.")
            return False
        
        # Test 5: Upload
        s3_key = self.test_upload_file(presigned_url_info)
        
        # Test 6: Verify Upload
        if s3_key:
            self.test_verify_upload(s3_key)
        
        # Test 7: Download URL
        self.test_generate_presigned_download_url()
        
        # Test 8: List bucket
        self.test_list_bucket_contents()
        
        # Generate report
        self.generate_test_report()
        
        return True


def main():
    """Main entry point"""
    try:
        test_suite = B2TestSuite()
        success = test_suite.run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

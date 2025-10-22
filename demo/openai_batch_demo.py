#!/usr/bin/env python3
"""
OpenAI Batch Job Demo Script

This script demonstrates how to create and monitor OpenAI batch jobs.
It creates a simple batch job with a few test requests and monitors its progress.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import requests
from dotenv import load_dotenv
import tempfile

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)


class OpenAIBatchDemo:
    """Demo class for OpenAI Batch API operations."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the demo with API key."""
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found! Please set OPENAI_API_KEY in demo/.env file "
                "or pass it as an argument."
            )

        self.base_url = "https://api.openai.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

    def create_batch_input_file(self, num_requests: int = 3) -> str:
        """
        Create a JSONL file with sample batch requests.

        Args:
            num_requests: Number of test requests to create

        Returns:
            Path to the created JSONL file
        """
        print(f"📝 Creating batch input file with {num_requests} requests...")

        # Create sample requests
        requests_data = []

        # Sample questions for the batch
        questions = [
            "What is the capital of France?",
            "Explain photosynthesis in simple terms.",
            "What are the primary colors?",
            "How does a computer work?",
            "What is machine learning?",
        ]

        for i in range(min(num_requests, len(questions))):
            request = {
                "custom_id": f"request-{i+1}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful assistant. Keep your responses brief."
                        },
                        {
                            "role": "user",
                            "content": questions[i]
                        }
                    ],
                    "max_tokens": 100,
                    "temperature": 0.7
                }
            }
            requests_data.append(request)

        # Write to JSONL file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False)
        for request in requests_data:
            temp_file.write(json.dumps(request) + '\n')
        temp_file.close()

        print(f"✅ Created batch input file: {temp_file.name}")
        return temp_file.name

    def upload_file(self, file_path: str) -> str:
        """
        Upload a file to OpenAI.

        Args:
            file_path: Path to the file to upload

        Returns:
            File ID from OpenAI
        """
        print(f"📤 Uploading file to OpenAI...")

        url = f"{self.base_url}/files"

        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f, 'application/jsonl')
            }
            data = {
                'purpose': 'batch'
            }

            response = requests.post(url, headers=self.headers, files=files, data=data)

        if response.status_code != 200:
            raise Exception(f"File upload failed: {response.status_code} - {response.text}")

        file_data = response.json()
        file_id = file_data['id']

        print(f"✅ File uploaded successfully!")
        print(f"   File ID: {file_id}")
        print(f"   Size: {file_data['bytes']} bytes")

        return file_id

    def create_batch(self, file_id: str) -> str:
        """
        Create a batch job.

        Args:
            file_id: ID of the uploaded file with batch requests

        Returns:
            Batch ID
        """
        print(f"🚀 Creating batch job...")

        url = f"{self.base_url}/batches"

        payload = {
            "input_file_id": file_id,
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h"
        }

        response = requests.post(
            url,
            headers={**self.headers, "Content-Type": "application/json"},
            json=payload
        )

        if response.status_code != 200:
            raise Exception(f"Batch creation failed: {response.status_code} - {response.text}")

        batch_data = response.json()
        batch_id = batch_data['id']

        print(f"✅ Batch job created successfully!")
        print(f"   Batch ID: {batch_id}")
        print(f"   Status: {batch_data['status']}")
        print(f"   Endpoint: {batch_data['endpoint']}")

        return batch_id

    def get_batch_status(self, batch_id: str) -> Dict:
        """
        Get the status of a batch job.

        Args:
            batch_id: ID of the batch job

        Returns:
            Batch status data
        """
        url = f"{self.base_url}/batches/{batch_id}"

        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            raise Exception(f"Failed to get batch status: {response.status_code} - {response.text}")

        return response.json()

    def monitor_batch(self, batch_id: str, check_interval: int = 5) -> Dict:
        """
        Monitor a batch job until completion.

        Args:
            batch_id: ID of the batch job to monitor
            check_interval: Seconds between status checks

        Returns:
            Final batch status data
        """
        print(f"\n📊 Monitoring batch job (checking every {check_interval} seconds)...")
        print("-" * 60)

        while True:
            batch_data = self.get_batch_status(batch_id)
            status = batch_data['status']

            # Display progress
            timestamp = datetime.now().strftime("%H:%M:%S")
            counts = batch_data.get('request_counts', {})

            print(f"[{timestamp}] Status: {status.upper()}")
            print(f"   Total: {counts.get('total', 0)} | "
                  f"Completed: {counts.get('completed', 0)} | "
                  f"Failed: {counts.get('failed', 0)}")

            # Check if job is complete
            if status in ['completed', 'failed', 'expired', 'cancelled']:
                print("-" * 60)
                print(f"\n🏁 Batch job finished with status: {status.upper()}")

                if status == 'completed':
                    print(f"✅ Output file ID: {batch_data.get('output_file_id', 'N/A')}")
                    if batch_data.get('error_file_id'):
                        print(f"⚠️  Error file ID: {batch_data['error_file_id']}")

                return batch_data

            time.sleep(check_interval)

    def download_results(self, file_id: str, output_path: Optional[str] = None) -> str:
        """
        Download results from a completed batch.

        Args:
            file_id: ID of the output file
            output_path: Optional path to save the file

        Returns:
            Path to the downloaded file
        """
        print(f"\n📥 Downloading results...")

        url = f"{self.base_url}/files/{file_id}/content"
        response = requests.get(url, headers=self.headers)

        if response.status_code != 200:
            raise Exception(f"Failed to download file: {response.status_code} - {response.text}")

        # Save to file
        if not output_path:
            output_path = f"batch_output_{file_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

        with open(output_path, 'wb') as f:
            f.write(response.content)

        print(f"✅ Results saved to: {output_path}")

        # Display sample results
        print("\n📋 Sample results:")
        print("-" * 60)
        with open(output_path, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines[:2], 1):  # Show first 2 results
                result = json.loads(line)
                custom_id = result.get('custom_id', 'N/A')

                if 'response' in result and 'body' in result['response']:
                    choices = result['response']['body'].get('choices', [])
                    if choices:
                        content = choices[0]['message']['content']
                        print(f"{custom_id}: {content[:100]}...")
                else:
                    print(f"{custom_id}: [No response]")

        if len(lines) > 2:
            print(f"... and {len(lines) - 2} more results")

        return output_path

    def run_demo(self, num_requests: int = 3, monitor: bool = True):
        """
        Run the complete batch job demo.

        Args:
            num_requests: Number of test requests to create
            monitor: Whether to monitor the job until completion
        """
        print("=" * 60)
        print("🎯 OpenAI Batch Job Demo")
        print("=" * 60)

        try:
            # Step 1: Create input file
            input_file = self.create_batch_input_file(num_requests)

            # Step 2: Upload file
            file_id = self.upload_file(input_file)

            # Step 3: Create batch job
            batch_id = self.create_batch(file_id)

            # Step 4: Monitor batch (optional)
            if monitor:
                batch_data = self.monitor_batch(batch_id)

                # Step 5: Download results if completed
                if batch_data['status'] == 'completed' and batch_data.get('output_file_id'):
                    self.download_results(batch_data['output_file_id'])
            else:
                print(f"\n💡 Batch job created! Check status with:")
                print(f"   python {sys.argv[0]} --check-batch {batch_id}")

            # Cleanup temp file
            os.unlink(input_file)

            print("\n✨ Demo completed successfully!")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            sys.exit(1)


def main():
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(
        description='OpenAI Batch Job Demo - Create and monitor batch jobs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Run demo with 3 test requests
  %(prog)s -n 5               # Run demo with 5 test requests
  %(prog)s --no-monitor       # Create batch without monitoring
  %(prog)s --check-batch ID   # Check status of existing batch
  %(prog)s --download FILE_ID # Download batch results

Environment:
  Set OPENAI_API_KEY in demo/.env file or export it:
  export OPENAI_API_KEY=your_api_key_here
        """
    )

    parser.add_argument(
        '-n', '--num-requests',
        type=int,
        default=3,
        help='Number of test requests to create (default: 3, max: 5)'
    )

    parser.add_argument(
        '--no-monitor',
        action='store_true',
        help='Create batch without monitoring its progress'
    )

    parser.add_argument(
        '--check-batch',
        metavar='BATCH_ID',
        help='Check the status of an existing batch job'
    )

    parser.add_argument(
        '--download',
        metavar='FILE_ID',
        help='Download results from a completed batch'
    )

    parser.add_argument(
        '--api-key',
        help='OpenAI API key (overrides environment variable)'
    )

    args = parser.parse_args()

    # Initialize demo
    try:
        demo = OpenAIBatchDemo(api_key=args.api_key)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # Handle different modes
    if args.check_batch:
        # Check batch status
        try:
            batch_data = demo.get_batch_status(args.check_batch)
            print(f"Batch ID: {batch_data['id']}")
            print(f"Status: {batch_data['status']}")
            print(f"Request counts: {batch_data.get('request_counts', {})}")
            if batch_data.get('output_file_id'):
                print(f"Output file: {batch_data['output_file_id']}")
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

    elif args.download:
        # Download results
        try:
            demo.download_results(args.download)
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

    else:
        # Run full demo
        num_requests = min(max(1, args.num_requests), 5)
        demo.run_demo(
            num_requests=num_requests,
            monitor=not args.no_monitor
        )


if __name__ == '__main__':
    main()
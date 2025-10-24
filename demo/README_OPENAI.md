# OpenAI Batch API Demo

A simple demonstration script that creates, monitors, and retrieves results from OpenAI Batch API jobs. Perfect for testing batch processing before integrating with TeckoChecker.

## Quick Start

```bash
# 1. Set up your API key
cd demo
echo "OPENAI_API_KEY=your_key_here" > .env

# 2. Install dependencies
pip install requests python-dotenv

# 3. Run the demo
python openai_batch_demo.py
```

## Key Features

- Creates batch jobs with sample chat completion requests
- Monitors batch job progress in real-time with status updates
- Automatically downloads and displays results when complete
- Supports checking existing batch status and downloading results separately
- Built-in error handling and progress tracking

## Additional Commands

```bash
# Create batch with 5 requests
python openai_batch_demo.py -n 5

# Create batch without monitoring
python openai_batch_demo.py --no-monitor

# Check existing batch status
python openai_batch_demo.py --check-batch batch_abc123

# Download results from completed batch
python openai_batch_demo.py --download file-abc123
```

## Learn More

For the full TeckoChecker polling orchestration system, see the [main README](../README.md).

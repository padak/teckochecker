# OpenAI Batch Job Demo

This demo script shows how to create and monitor OpenAI batch jobs using the Batch API.

## Features

- ✨ Creates sample batch requests automatically
- 📤 Uploads batch input file to OpenAI
- 🚀 Creates and submits batch job
- 📊 Monitors batch progress in real-time
- 📥 Downloads and displays results when completed
- 🛠️ Command-line interface with multiple options

## Setup

### Prerequisites

Before running this demo, make sure you have **TeckoChecker properly set up** by following the [main setup guide](../docs/SETUP.md).

This includes:
- Python virtual environment activated
- All dependencies installed
- Main project working correctly

### Configure Demo API Key

```bash
# From the demo directory
cp .env.example .env

# Edit .env and add your OpenAI API key
# Get your key from: https://platform.openai.com/api-keys
nano .env
```

## Usage

### Basic Usage

Run the demo with default settings (3 test requests):
```bash
python openai_batch_demo.py
```

### Command Options

```bash
# Create batch with 5 test requests
python openai_batch_demo.py -n 5

# Create batch without monitoring (returns immediately)
python openai_batch_demo.py --no-monitor

# Check status of existing batch
python openai_batch_demo.py --check-batch batch_abc123

# Download results from completed batch
python openai_batch_demo.py --download file-xyz789

# Show help
python openai_batch_demo.py --help
```

### Environment Variables

You can set these in your `.env` file:
- `OPENAI_API_KEY` - Required: Your OpenAI API key

## How It Works

1. **Create Input File**: The script generates a JSONL file with sample chat completion requests
2. **Upload File**: Uploads the JSONL file to OpenAI with purpose "batch"
3. **Create Batch**: Submits a batch job with the uploaded file
4. **Monitor Progress**: Polls the batch status every 5 seconds
5. **Download Results**: When completed, downloads and displays the results

## Batch Request Format

Each line in the batch input file follows this structure:
```json
{
  "custom_id": "request-1",
  "method": "POST",
  "url": "/v1/chat/completions",
  "body": {
    "model": "gpt-3.5-turbo",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is the capital of France?"}
    ],
    "max_tokens": 100
  }
}
```

## Sample Questions

The demo includes these sample questions:
- What is the capital of France?
- Explain photosynthesis in simple terms
- What are the primary colors?
- How does a computer work?
- What is machine learning?

## Batch Job Lifecycle

1. **validating** - Initial validation of input file
2. **in_progress** - Processing requests
3. **finalizing** - Preparing results
4. **completed** - Job finished successfully
5. **failed/cancelled/expired** - Job ended with error

## Cost Considerations

- Batch API offers 50% discount compared to regular API calls
- Processing happens within 24-hour window
- Ideal for non-urgent, large-scale processing

## Troubleshooting

If you encounter errors:
1. Verify your API key is correct in `.env`
2. Check you have sufficient API credits
3. Ensure your requests are properly formatted
4. Monitor the error_file_id if batch fails

## Keboola Integration Demo

This directory also contains a **Keboola Custom Python Script** (`main.py`) that demonstrates how to receive batch completion metadata from TeckoChecker.

**Use case**: When TeckoChecker finishes monitoring your OpenAI batches, it can automatically trigger a Keboola configuration with batch metadata (completed/failed batch IDs, counts, etc.).

See [README_KEBOOLA.md](README_KEBOOLA.md) for:
- How to set up the Keboola Custom Python configuration
- How to connect TeckoChecker to trigger Keboola jobs
- Example customizations (download results, send notifications, write to Storage)

## Links

- [OpenAI Batch API Docs](https://platform.openai.com/docs/guides/batch)
- [API Reference](https://platform.openai.com/docs/api-reference/batch)
- [Get API Key](https://platform.openai.com/api-keys)
- [Keboola Integration Guide](README_KEBOOLA.md)
# TeckoChecker Demo - Keboola Custom Python Script

This demo script (`main.py`) shows how to receive and process batch completion metadata from TeckoChecker in Keboola Connection.

## What This Script Does

When TeckoChecker finishes monitoring OpenAI batch jobs, it automatically triggers your Keboola configuration with metadata about:
- Which batches completed successfully
- Which batches failed/were cancelled/expired
- Total counts and batch IDs

This demo script receives that metadata and logs it to Keboola events.

## Parameters Received from TeckoChecker

TeckoChecker passes these parameters automatically:

```json
{
  "batch_ids_completed": ["batch_abc123", "batch_def456"],
  "batch_ids_failed": ["batch_ghi789"],
  "batch_count_total": 3,
  "batch_count_completed": 2,
  "batch_count_failed": 1
}
```

## Setup in Keboola Connection

### Step 1: Create Custom Python Configuration

1. Go to **Components** in your Keboola project
2. Search for **"Custom Python Script"** (component ID: `kds-team.app-custom-python`)
3. Click **"+ New Configuration"**
4. Give it a name like `"TeckoChecker Demo"`

### Step 2: Configure the Script

In the configuration editor:

1. **Python Version**: Select `3.13` (or latest available)
2. **Code Source**: Select `code` (inline code editor)
3. **Script**: Paste the contents of `main.py` into the code editor

### Step 3: Get Configuration ID

After saving, note your **Configuration ID** from the URL or configuration detail page.

### Step 4: Configure TeckoChecker

Create a polling job in TeckoChecker pointing to this Keboola configuration:

```bash
teckochecker job create \
  --name "My Multi-Batch Job" \
  -b batch_abc123 \
  -b batch_def456 \
  -b batch_ghi789 \
  --openai-secret openai-prod \
  --keboola-secret keboola-prod \
  --keboola-stack "https://connection.keboola.com" \
  --component-id "kds-team.app-custom-python" \
  --config-id "YOUR-CONFIG-ID"
```

## How It Works

### TeckoChecker Flow

1. **Monitoring**: TeckoChecker polls OpenAI for batch status every X seconds
2. **Completion**: When all batches reach terminal state
3. **Trigger**: TeckoChecker triggers your Keboola configuration via API
4. **Parameters**: Batch metadata is passed as `configData.parameters`
5. **Execution**: Keboola runs your Custom Python script with those parameters

### Script Flow

```python
# 1. Initialize Keboola interface
ci = CommonInterface()
parameters = ci.configuration.parameters

# 2. Extract batch metadata
batch_ids_completed = parameters.get("batch_ids_completed", [])
batch_ids_failed = parameters.get("batch_ids_failed", [])

# 3. Log summary
logging.info(f"Total: {batch_count_total}")
logging.info(f"Completed: {batch_count_completed}")
logging.info(f"Failed: {batch_count_failed}")

# 4. Process results
process_batch_results(batch_ids_completed, batch_ids_failed)
```

## Customizing the Script

### Add OpenAI Integration

Download completed batch results:

```python
import openai

def download_batch_results(batch_id: str) -> None:
    """Download results from completed OpenAI batch."""
    client = openai.OpenAI(api_key=parameters.get("#openai_api_key"))

    # Get batch details
    batch = client.batches.retrieve(batch_id)

    # Download output file
    if batch.output_file_id:
        content = client.files.content(batch.output_file_id)
        # Process content...
```

### Add Notification Logic

```python
def send_completion_notification(batch_count: int, failed_count: int) -> None:
    """Send notification about batch completion."""
    if failed_count == 0:
        send_slack_message(f"All {batch_count} batches completed!")
    else:
        send_slack_message(f"{failed_count}/{batch_count} batches failed")
```

### Write Results to Keboola Storage

```python
import csv
from keboola.component import CommonInterface

def write_batch_results(ci: CommonInterface, parameters: dict) -> None:
    """Write batch results to Keboola Storage."""
    out_table_path = ci.create_out_table_definition(
        "batch_results.csv",
        primary_key=["batch_id"]
    )

    with open(out_table_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["batch_id", "status"])
        writer.writeheader()

        for batch_id in parameters.get("batch_ids_completed", []):
            writer.writerow({"batch_id": batch_id, "status": "completed"})

        for batch_id in parameters.get("batch_ids_failed", []):
            writer.writerow({"batch_id": batch_id, "status": "failed"})
```

## Testing

### Local Testing (Optional)

```bash
mkdir -p /data/config
cat > /data/config/config.json << 'EOF'
{
  "parameters": {
    "batch_ids_completed": ["batch_test123", "batch_test456"],
    "batch_ids_failed": ["batch_test789"],
    "batch_count_total": 3,
    "batch_count_completed": 2,
    "batch_count_failed": 1
  }
}
EOF

python main.py
```

### Testing in Keboola

1. Open your Custom Python configuration
2. Click **"Run Component"**
3. Add test parameters manually
4. Check **"Events"** tab for logged output

## Expected Output

```
================================================================================
TeckoChecker Batch Completion Summary
================================================================================
Total Batches: 3
Completed: 2
Failed: 1

Completed Batch IDs:
  1. batch_abc123
  2. batch_def456

Failed Batch IDs:
  1. batch_ghi789
================================================================================
Partial success: 2/3 batches completed

Processing batch results...
Processing 2 completed batches...
  - Would download/process results from: batch_abc123
  - Would download/process results from: batch_def456
Handling 1 failed batches...
  - Would handle failure for: batch_ghi789
Processing complete!

TeckoChecker Demo Script Completed Successfully
```

## Next Steps

1. **Customize**: Add your own processing logic in `process_batch_results()`
2. **Integrate**: Connect to OpenAI API to download actual batch results
3. **Store**: Write results to Keboola Storage tables
4. **Notify**: Send notifications to Slack, email, or other systems
5. **Orchestrate**: Trigger additional Keboola flows based on completion status

## Troubleshooting

### Script Not Receiving Parameters

Check that:
- TeckoChecker configuration has correct `component-id` and `config-id`
- Keboola secret has valid API token with write permissions
- TeckoChecker logs show successful Keboola trigger

### Parameters Are Empty

Verify:
- TeckoChecker is running: `python teckochecker.py start`
- Polling job is active: `teckochecker job list`
- OpenAI batches exist and are reachable

### Script Fails to Run

Check:
- Python version is compatible (3.11+)
- `keboola.component` library is available
- Script syntax is valid

## Resources

- [TeckoChecker Documentation](../docs/USER_GUIDE.md)
- [Keboola Custom Python Documentation](https://github.com/keboola/component-custom-python)
- [OpenAI Batch API Documentation](https://platform.openai.com/docs/api-reference/batch)

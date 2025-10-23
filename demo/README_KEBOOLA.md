# TeckoChecker Demo - Keboola Custom Python Script

This demo script receives batch completion metadata from TeckoChecker and processes it in Keboola Connection. When TeckoChecker finishes monitoring OpenAI batches, it triggers your Keboola configuration with completion status, batch IDs, and counts.

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

## Setup Steps

1. **Create Keboola Configuration**
   - Go to Components > Custom Python Script (`kds-team.app-custom-python`)
   - Create new configuration, select Python 3.13+
   - Paste `keboola_batch_handler.py` contents into the code editor
   - Save and note the Configuration ID

2. **Create TeckoChecker Polling Job**

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

1. TeckoChecker polls OpenAI for batch status
2. When all batches reach terminal state, TeckoChecker triggers your Keboola configuration
3. Batch metadata is passed as `configData.parameters`
4. Your script processes the results:

```python
ci = CommonInterface()
parameters = ci.configuration.parameters
batch_ids_completed = parameters.get("batch_ids_completed", [])
batch_ids_failed = parameters.get("batch_ids_failed", [])
# Process your batches...
```

## Customization Example

Download and process OpenAI batch results:

```python
import openai

def download_batch_results(batch_id: str) -> None:
    client = openai.OpenAI(api_key=parameters.get("#openai_api_key"))
    batch = client.batches.retrieve(batch_id)

    if batch.output_file_id:
        content = client.files.content(batch.output_file_id)
        # Process content, write to Keboola Storage, send notifications, etc.
```

## Testing

**In Keboola**: Click "Run Component" in your configuration, add test parameters, check Events tab for output.

**Locally** (optional):
```bash
mkdir -p /data/config
cat > /data/config/config.json << 'EOF'
{"parameters": {"batch_ids_completed": ["batch_test123"], "batch_ids_failed": [], "batch_count_total": 1, "batch_count_completed": 1, "batch_count_failed": 0}}
EOF
python keboola_batch_handler.py
```

## Expected Output

```
================================================================================
TeckoChecker Batch Completion Summary
================================================================================
Total Batches: 3 | Completed: 2 | Failed: 1

Completed Batch IDs: batch_abc123, batch_def456
Failed Batch IDs: batch_ghi789
================================================================================
Processing complete!
```

## Troubleshooting

**No parameters received?**
- Verify correct `component-id` and `config-id` in TeckoChecker
- Check Keboola secret has valid API token with write permissions
- Review TeckoChecker logs for trigger confirmation

**Empty parameters?**
- Ensure TeckoChecker is running: `python teckochecker.py start`
- Verify polling job is active: `teckochecker job list`
- Confirm OpenAI batches exist and are accessible

**Script fails?**
- Check Python version compatibility (3.11+)
- Verify `keboola.component` library is available
- Validate script syntax

## Resources

- [TeckoChecker User Guide](../docs/USER_GUIDE.md)
- [Keboola Custom Python](https://github.com/keboola/component-custom-python)
- [OpenAI Batch API](https://platform.openai.com/docs/api-reference/batch)

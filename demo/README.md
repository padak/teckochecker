# TeckoChecker Demos

This directory contains practical demos showing how to use TeckoChecker with OpenAI Batch API and Keboola Connection.

## Demos

### 1. OpenAI Batch API Demo

Standalone script demonstrating OpenAI Batch API operations: create batch jobs, monitor progress, and download results.

**See**: [README_OPENAI.md](README_OPENAI.md)

**Quick start**:
```bash
cd demo
cp .env.example .env  # Add your OPENAI_API_KEY
python openai_batch_demo.py
```

### 2. Keboola Integration Demo

Keboola Custom Python script that receives batch completion metadata from TeckoChecker and processes results.

**See**: [README_KEBOOLA.md](README_KEBOOLA.md)

**Quick start**:
```bash
# Deploy keboola_batch_handler.py to Keboola Custom Python
# Configure TeckoChecker polling job to trigger your Keboola config
```

## Prerequisites

- TeckoChecker installed and configured (see [main setup guide](../docs/SETUP.md))
- Python 3.11+ with virtual environment activated
- For OpenAI demo: OpenAI API key with credits
- For Keboola demo: Keboola Connection project with Custom Python component

## What You'll Learn

- **OpenAI Demo**: How to use Batch API for cost-effective bulk processing (50% discount)
- **Keboola Demo**: How to integrate TeckoChecker with downstream workflows in Keboola

## Resources

- [OpenAI Batch API Docs](https://platform.openai.com/docs/guides/batch)
- [Keboola Custom Python Component](https://help.keboola.com/components/extractors/other/custom-python/)
- [TeckoChecker User Guide](../docs/USER_GUIDE.md)
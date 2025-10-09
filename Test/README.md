# Intent Recognition Testing Guide

## Overview

This guide describes how to run intent recognition accuracy tests for the Smart Home AI Assistant system. The testing framework evaluates the system's ability to correctly understand and extract IoT control commands from natural language inputs, including handling of typos and spelling errors.

## Testing Architecture

The testing system consists of three main components:

1. **Test Case Generator** (`test_case_generator.py`) - Generates baseline test cases with correct spelling
2. **Typo Test Case Generator** (`test_case_generator_typo.py`) - Generates fault-tolerance test cases with various spelling errors
3. **Intent Accuracy Tester** (`intent_accuracy_test.py`) - Executes tests and generates accuracy reports

## Prerequisites

- All Docker services must be running (`docker-compose up -d`)
- The test-runner container must be active
- Coordinator service must be accessible at `http://coordinator:8080`

## Quick Start

### Step 1: Access the Test Container

```bash
docker exec -it ai-assistant-test-runner bash
```

### Step 2: Generate Test Cases

Generate baseline test cases (correct spelling):
```bash
python /app/test_case_generator.py
```

Generate typo test cases (fault tolerance):
```bash
python /app/test_case_generator_typo.py
```

**Output:** Test case files will be created in `/app/test_cases/` directory.

### Step 3: Run Accuracy Tests

Execute the intent recognition test:
```bash
python /app/intent_accuracy_test.py \
  --test-file /app/test_cases/simple_light_control_typo_test_cases.json \
  --coordinator-url http://coordinator:8080 \
  --output-dir /app/results
```

### Step 4: Review Results

Test results will be saved in `/app/results/` directory:
- `accuracy_report_YYYYMMDD_HHMMSS.json` - Detailed JSON report
- `accuracy_results_YYYYMMDD_HHMMSS.csv` - CSV data for analysis



## Test Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--test-file` | Path to test cases JSON file | Required |
| `--coordinator-url` | URL of coordinator service | `http://localhost:8080` |
| `--output-dir` | Directory for test results | `./test_results` |
| `--delay` | Delay between tests (seconds) | `1.0` |
| `--generate-examples` | Generate example test cases | N/A |

## Test Case Format

Test cases follow this JSON structure:

```json
{
  "id": "test_001",
  "input": "Turn on the living room lights",
  "expected_devices": ["ceiling_light"],
  "expected_locations": ["living_room"],
  "expected_actions": ["on"],
  "description": "Simple light control command",
  "category": "baseline"
}
```

### Categories

- **baseline** - Standard commands with correct spelling
- **fault_tolerance** - Commands with spelling errors
- **multilingual** - Commands in different languages
- **discrimination** - Non-control queries to test false positives

## Understanding Test Results

### JSON Report Structure

```json
{
  "summary": {
    "total_tests": 100,
    "successful_requests": 98,
    "overall_accuracy": 0.95,
    "average_device_f1": 0.96,
    "average_location_f1": 0.94,
    "average_action_f1": 0.97,
    "average_response_time": 1.23
  },
  "category_summary": {
    "baseline": {
      "total": 50,
      "correct": 48,
      "accuracy": 0.96
    },
    "fault_tolerance": {
      "total": 50,
      "correct": 45,
      "accuracy": 0.90
    }
  },
  "detailed_results": [...]
}
```

### Key Metrics

- **Overall Accuracy**: Percentage of tests where all parameters (device, location, action) were correctly extracted
- **F1 Score**: Harmonic mean of precision and recall for each parameter type
- **Response Time**: Average time to process each command
- **Category Accuracy**: Accuracy breakdown by test category

### CSV Report Columns

| Column | Description |
|--------|-------------|
| `test_id` | Unique test identifier |
| `category` | Test category |
| `input` | Input command text |
| `overall_correct` | Boolean indicating perfect extraction |
| `device_f1` | F1 score for device extraction |
| `location_f1` | F1 score for location extraction |
| `action_f1` | F1 score for action extraction |
| `response_time` | Processing time in seconds |
| `expected_devices` | Expected device types |
| `actual_devices` | Extracted device types |

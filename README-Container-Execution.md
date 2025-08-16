# Jenkins Container Execution Pipeline

This document describes the Jenkins pipeline for executing App1 and App2 applications using Docker containers pulled from JFrog Artifactory.

## Overview

The `Jenkinsfile-container-execution` pipeline provides a comprehensive solution for:
- Pulling Docker containers from JFrog Artifactory
- Executing App1 (Excel Generator) and App2 (Excel Processor) in separate stages
- Passing command-line parameters to containerized applications
- Proper resource cleanup and error handling

## Pipeline Features

### 🚀 **Container Management**
- Pulls Docker images from JFrog Artifactory (`trialqlk1tc.jfrog.io/dockertest-docker`)
- Runs containers with resource limits (512MB memory, 1 CPU)
- Automatic container cleanup with `--rm` flag
- Timeout handling (5 minutes per container)

### 📊 **Application Execution**
- **App1 Stage**: Excel Generator with configurable parameters
- **App2 Stage**: Excel Processor that processes App1 output
- Volume mounts for data sharing between host and containers
- Parameter passing via command-line arguments

### 🧹 **Resource Cleanup**
- Automatic cleanup in `post-always` block
- Removes containers, images, volumes, and networks
- Runs regardless of pipeline success or failure
- Configurable image cleanup option

### 🛡️ **Error Handling**
- Comprehensive try-catch blocks
- Container log retrieval for debugging
- Timeout protection against hanging containers
- Graceful failure handling

## Pipeline Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `IMAGE_TAG` | String | `latest` | Docker image tag to pull |
| `APP1_OUTPUT_FILE` | String | `business_report.xlsx` | App1 output filename |
| `APP1_RECORDS` | String | `1000` | Number of records to generate |
| `APP1_FORMAT` | Choice | `business` | Data format (business/financial/customer) |
| `APP1_SHEETS` | String | `3` | Number of Excel sheets |
| `APP2_INPUT_FILE` | String | `business_report.xlsx` | App2 input filename |
| `APP2_ANALYSIS_TYPE` | String | `full` | Analysis type for App2 |
| `CLEANUP_IMAGES` | Boolean | `true` | Remove images after execution |

## App1 Excel Generator

### Enhanced Features

The `app1/src/excel_generator.py` has been enhanced to accept command-line arguments:

```python
python excel_generator.py --output report.xlsx --records 5000 --format financial --sheets 3
```

### Command-Line Arguments

| Argument | Short | Type | Default | Description |
|----------|-------|------|---------|-------------|
| `--output` | `-o` | String | `generated_data.xlsx` | Output Excel filename |
| `--records` | `-r` | Integer | `1000` | Records per sheet |
| `--format` | `-f` | Choice | `business` | Data format type |
| `--sheets` | `-s` | Integer | `1` | Number of sheets |
| `--seed` | | Integer | `42` | Random seed |

### Data Formats

1. **Business Format**: Company data with contact information, revenue, employees
2. **Financial Format**: Transaction data with accounts, amounts, currencies
3. **Customer Format**: Customer profiles with demographics and purchase history

### Usage Examples

```bash
# Basic usage
python excel_generator.py --output sales_data.xlsx --records 2000

# Financial data with multiple sheets
python excel_generator.py -o financial_report.xlsx -r 5000 -f financial -s 5

# Customer data with custom seed
python excel_generator.py --format customer --records 3000 --seed 123
```

## Pipeline Usage

### 1. Manual Execution

Navigate to your Jenkins job and click "Build with Parameters":

```
IMAGE_TAG: latest
APP1_OUTPUT_FILE: quarterly_report.xlsx
APP1_RECORDS: 5000
APP1_FORMAT: financial
APP1_SHEETS: 4
APP2_INPUT_FILE: quarterly_report.xlsx
APP2_ANALYSIS_TYPE: full
CLEANUP_IMAGES: true
```

### 2. Programmatic Execution

Using Jenkins API:

```bash
curl -X POST "http://jenkins-server/job/your-job/buildWithParameters" \
  --user "username:token" \
  --data-urlencode "IMAGE_TAG=latest" \
  --data-urlencode "APP1_OUTPUT_FILE=custom_report.xlsx" \
  --data-urlencode "APP1_RECORDS=10000" \
  --data-urlencode "APP1_FORMAT=business"
```

## Pipeline Stages

### 1. Initialize
- Sets up workspace directories (`output`, `input`, `reports`)
- Displays configuration parameters
- Prepares environment variables

### 2. Docker Login
- Authenticates with JFrog Artifactory
- Uses `artifactory-credentials` from Jenkins

### 3. Pull App1 Container
- Pulls `app1:${IMAGE_TAG}` from registry
- Verifies successful pull

### 4. Execute App1
- Runs Excel Generator with specified parameters
- Mounts output directory
- Applies resource limits and timeout
- Verifies output file creation

### 5. Pull App2 Container
- Pulls `app2:${IMAGE_TAG}` from registry
- Runs in parallel with App1 execution

### 6. Execute App2
- Transfers App1 output to App2 input
- Runs Excel Processor with parameters
- Mounts input, output, and reports directories

### 7. Summary
- Displays execution results
- Shows file locations and parameters used

## Directory Structure

```
Jenkins Workspace/
├── input/           # App2 input files
├── output/          # App1 output files
├── reports/         # App2 analysis reports
└── Jenkinsfile-container-execution
```

## Docker Container Execution

### App1 Container Command
```bash
docker run --rm \
  -v "${OUTPUT_DIR}:/app/output" \
  -v "${INPUT_DIR}:/app/input" \
  --memory="512m" \
  --cpus="1.0" \
  --name "app1-${BUILD_NUMBER}" \
  trialqlk1tc.jfrog.io/dockertest-docker/app1:latest \
  python src/excel_generator.py --output "report.xlsx" --records 1000 --format business --sheets 3
```

### App2 Container Command
```bash
docker run --rm \
  -v "${OUTPUT_DIR}:/app/output" \
  -v "${INPUT_DIR}:/app/input" \
  -v "${REPORTS_DIR}:/app/reports" \
  --memory="512m" \
  --cpus="1.0" \
  --name "app2-${BUILD_NUMBER}" \
  trialqlk1tc.jfrog.io/dockertest-docker/app2:latest \
  python processor_main.py --input "report.xlsx" --analysis full
```

## Error Handling

### Container Failures
- Pipeline captures container exit codes
- Retrieves container logs for debugging
- Stops execution and reports failure

### Resource Issues
- Memory and CPU limits prevent resource exhaustion
- Timeout prevents hanging containers
- Automatic cleanup prevents resource leaks

### Network Issues
- Retry logic for Docker pulls
- Proper error messages for connectivity issues
- Graceful degradation when possible

## Cleanup Process

### Automatic Cleanup (post-always)
1. **Containers**: Stop and remove all job-related containers
2. **Images**: Remove pulled images (if `CLEANUP_IMAGES=true`)
3. **Volumes**: Prune dangling volumes
4. **Networks**: Prune unused networks

### Manual Cleanup
```bash
# Remove specific containers
docker rm -f app1-${BUILD_NUMBER} app2-${BUILD_NUMBER}

# Remove images
docker rmi trialqlk1tc.jfrog.io/dockertest-docker/app1:latest
docker rmi trialqlk1tc.jfrog.io/dockertest-docker/app2:latest

# System cleanup
docker system prune -f
```

## Troubleshooting

### Common Issues

1. **Image Pull Failures**
   - Check Artifactory credentials
   - Verify image tag exists
   - Check network connectivity

2. **Container Execution Failures**
   - Review container logs in pipeline output
   - Check resource limits
   - Verify volume mount paths

3. **Parameter Issues**
   - Validate parameter formats
   - Check file path accessibility
   - Ensure numeric parameters are valid

### Debug Commands

```bash
# Check running containers
docker ps --filter "name=app1-" --filter "name=app2-"

# View container logs
docker logs app1-${BUILD_NUMBER}
docker logs app2-${BUILD_NUMBER}

# Check disk space
docker system df

# Inspect images
docker inspect trialqlk1tc.jfrog.io/dockertest-docker/app1:latest
```

## Best Practices

1. **Resource Management**
   - Use appropriate memory and CPU limits
   - Enable image cleanup for disk space management
   - Monitor container resource usage

2. **Parameter Validation**
   - Validate numeric parameters before execution
   - Use meaningful default values
   - Provide clear parameter descriptions

3. **Error Recovery**
   - Implement retry logic for transient failures
   - Provide detailed error messages
   - Archive logs for post-mortem analysis

4. **Security**
   - Use non-root users in containers
   - Limit container capabilities
   - Secure credential management

## Integration with Existing Pipeline

This container execution pipeline complements the existing `Jenkinsfile` which builds and pushes images. The typical workflow:

1. **Development**: Use existing `Jenkinsfile` to build and push images
2. **Execution**: Use `Jenkinsfile-container-execution` to run applications
3. **Testing**: Validate outputs and reports
4. **Deployment**: Promote successful builds to production

## Monitoring and Logging

- All stages provide detailed logging
- Container execution logs are captured
- Build artifacts are archived automatically
- Resource usage is monitored and reported

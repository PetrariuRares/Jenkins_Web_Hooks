# Usage Examples for Container Execution Pipeline

This document provides practical examples of how to use the Jenkins Container Execution Pipeline.

## Quick Start Examples

### Example 1: Basic Business Report Generation

**Jenkins Parameters:**
```
IMAGE_TAG: latest
APP1_OUTPUT_FILE: monthly_business_report.xlsx
APP1_RECORDS: 2500
APP1_FORMAT: business
APP1_SHEETS: 2
APP2_INPUT_FILE: monthly_business_report.xlsx
APP2_ANALYSIS_TYPE: full
CLEANUP_IMAGES: true
```

**Expected Output:**
- Excel file with 2 sheets, 2500 business records each
- Summary statistics in JSON format
- Distribution charts for numeric columns
- Correlation heatmap
- Overall analysis report

### Example 2: Financial Data Analysis

**Jenkins Parameters:**
```
IMAGE_TAG: latest
APP1_OUTPUT_FILE: financial_transactions.xlsx
APP1_RECORDS: 10000
APP1_FORMAT: financial
APP1_SHEETS: 5
APP2_INPUT_FILE: financial_transactions.xlsx
APP2_ANALYSIS_TYPE: charts
CLEANUP_IMAGES: false
```

**Expected Output:**
- Excel file with 5 sheets, 10000 financial transactions each
- Chart visualizations only (no summary statistics)
- Distribution plots for amounts, balances, fees
- Images kept for further analysis

### Example 3: Customer Data Processing

**Jenkins Parameters:**
```
IMAGE_TAG: dev
APP1_OUTPUT_FILE: customer_database.xlsx
APP1_RECORDS: 5000
APP1_FORMAT: customer
APP1_SHEETS: 3
APP2_INPUT_FILE: customer_database.xlsx
APP2_ANALYSIS_TYPE: summary
CLEANUP_IMAGES: true
```

**Expected Output:**
- Excel file with 3 sheets, 5000 customer records each
- Summary statistics only (no charts)
- JSON reports with data insights

## Command-Line Equivalents

### App1 Excel Generator Commands

The Jenkins pipeline translates parameters into these container commands:

```bash
# Example 1: Business Report
docker run --rm \
  -v "${OUTPUT_DIR}:/app/output" \
  trialqlk1tc.jfrog.io/dockertest-docker/app1:latest \
  python src/excel_generator.py \
    --output "monthly_business_report.xlsx" \
    --records 2500 \
    --format business \
    --sheets 2

# Example 2: Financial Data
docker run --rm \
  -v "${OUTPUT_DIR}:/app/output" \
  trialqlk1tc.jfrog.io/dockertest-docker/app1:latest \
  python src/excel_generator.py \
    --output "financial_transactions.xlsx" \
    --records 10000 \
    --format financial \
    --sheets 5

# Example 3: Customer Data
docker run --rm \
  -v "${OUTPUT_DIR}:/app/output" \
  trialqlk1tc.jfrog.io/dockertest-docker/app1:latest \
  python src/excel_generator.py \
    --output "customer_database.xlsx" \
    --records 5000 \
    --format customer \
    --sheets 3
```

### App2 Excel Processor Commands

```bash
# Example 1: Full Analysis
docker run --rm \
  -v "${INPUT_DIR}:/app/input" \
  -v "${REPORTS_DIR}:/app/reports" \
  trialqlk1tc.jfrog.io/dockertest-docker/app2:latest \
  python processor_main.py \
    --input "monthly_business_report.xlsx" \
    --analysis full

# Example 2: Charts Only
docker run --rm \
  -v "${INPUT_DIR}:/app/input" \
  -v "${REPORTS_DIR}:/app/reports" \
  trialqlk1tc.jfrog.io/dockertest-docker/app2:latest \
  python processor_main.py \
    --input "financial_transactions.xlsx" \
    --analysis charts

# Example 3: Summary Only
docker run --rm \
  -v "${INPUT_DIR}:/app/input" \
  -v "${REPORTS_DIR}:/app/reports" \
  trialqlk1tc.jfrog.io/dockertest-docker/app2:latest \
  python processor_main.py \
    --input "customer_database.xlsx" \
    --analysis summary
```

## Advanced Usage Scenarios

### Scenario 1: Large Dataset Processing

For processing large datasets with memory optimization:

**Jenkins Parameters:**
```
IMAGE_TAG: latest
APP1_OUTPUT_FILE: large_dataset.xlsx
APP1_RECORDS: 50000
APP1_FORMAT: financial
APP1_SHEETS: 1
APP2_INPUT_FILE: large_dataset.xlsx
APP2_ANALYSIS_TYPE: summary
CLEANUP_IMAGES: true
```

**Notes:**
- Single sheet to reduce memory usage
- Summary analysis only to avoid memory-intensive chart generation
- Automatic cleanup to free disk space

### Scenario 2: Multi-Format Analysis

Generate different data formats for comprehensive testing:

**Pipeline Sequence:**
1. Run with `APP1_FORMAT: business`
2. Run with `APP1_FORMAT: financial`  
3. Run with `APP1_FORMAT: customer`

Each run produces different data structures for testing various scenarios.

### Scenario 3: Development Testing

Using development images with custom parameters:

**Jenkins Parameters:**
```
IMAGE_TAG: feature-branch-name
APP1_OUTPUT_FILE: test_data.xlsx
APP1_RECORDS: 100
APP1_FORMAT: business
APP1_SHEETS: 1
APP2_INPUT_FILE: test_data.xlsx
APP2_ANALYSIS_TYPE: full
CLEANUP_IMAGES: false
```

**Notes:**
- Small dataset for quick testing
- Keep images for debugging
- Use feature branch images

## Output File Examples

### App1 Generated Excel Structure

**Business Format:**
```
Sheet: Business_Data_1
Columns: ID, Company, Contact_Name, Email, Phone, Address, City, State, ZIP, 
         Country, Industry, Revenue, Employees, Founded, Website, Description, 
         Last_Contact, Status
```

**Financial Format:**
```
Sheet: Financial_Data_1
Columns: Transaction_ID, Date, Account_Number, Account_Name, Transaction_Type, 
         Amount, Balance, Currency, Description, Category, Branch, Reference, 
         Status, Fee
```

**Customer Format:**
```
Sheet: Customer_Data_1
Columns: Customer_ID, First_Name, Last_Name, Email, Phone, Date_of_Birth, 
         Gender, Address, City, State, ZIP, Country, Registration_Date, 
         Last_Login, Total_Orders, Total_Spent, Preferred_Category, 
         Loyalty_Points, Status, Marketing_Consent
```

### App2 Generated Reports

**Summary Files:**
- `Business_Data_1_summary.json`
- `Financial_Data_1_summary.json`
- `Customer_Data_1_summary.json`

**Chart Files:**
- `Business_Data_1_Revenue_distribution.png`
- `Business_Data_1_Employees_distribution.png`
- `Business_Data_1_correlation_heatmap.png`

**Overall Report:**
- `overall_analysis_report.json`

## Troubleshooting Examples

### Issue 1: Container Pull Failure

**Error:** `Failed to pull App1 container`

**Solution:**
```bash
# Check if image exists in registry
docker search trialqlk1tc.jfrog.io/dockertest-docker/app1

# Verify credentials
docker login trialqlk1tc.jfrog.io

# Try manual pull
docker pull trialqlk1tc.jfrog.io/dockertest-docker/app1:latest
```

### Issue 2: Parameter Validation Error

**Error:** `Invalid number of records: abc`

**Solution:**
- Ensure `APP1_RECORDS` contains only numeric values
- Use default values for testing: `1000`
- Check parameter types in Jenkins job configuration

### Issue 3: Output File Not Found

**Error:** `App1 output file not found`

**Solution:**
```bash
# Check container logs
docker logs app1-${BUILD_NUMBER}

# Verify output directory permissions
ls -la ${WORKSPACE}/output/

# Check disk space
df -h
```

## Performance Optimization

### Memory Usage

**Small Dataset (< 1000 records):**
- Memory Limit: 256MB
- Expected Processing Time: < 30 seconds

**Medium Dataset (1000-10000 records):**
- Memory Limit: 512MB (default)
- Expected Processing Time: 1-3 minutes

**Large Dataset (> 10000 records):**
- Memory Limit: 1GB
- Expected Processing Time: 3-10 minutes

### Disk Space Management

**Cleanup Strategy:**
```bash
# Enable image cleanup for production
CLEANUP_IMAGES: true

# Monitor disk usage
docker system df

# Manual cleanup if needed
docker system prune -f
```

## Integration Examples

### With Existing CI/CD Pipeline

```groovy
// Build images first
build job: 'docker-build-pipeline', parameters: [
    string(name: 'BRANCH_NAME', value: env.BRANCH_NAME)
]

// Then execute containers
build job: 'container-execution-pipeline', parameters: [
    string(name: 'IMAGE_TAG', value: env.BRANCH_NAME),
    string(name: 'APP1_RECORDS', value: '5000'),
    string(name: 'APP1_FORMAT', value: 'business')
]
```

### With Notification Systems

```groovy
post {
    success {
        emailext (
            subject: "Container Execution Success: ${env.JOB_NAME} - ${env.BUILD_NUMBER}",
            body: "Excel processing completed successfully. Reports available in build artifacts.",
            to: "${env.CHANGE_AUTHOR_EMAIL}"
        )
    }
    failure {
        slackSend (
            color: 'danger',
            message: "Container execution failed: ${env.JOB_NAME} - ${env.BUILD_NUMBER}"
        )
    }
}
```

## Best Practices Summary

1. **Start Small**: Use small datasets for initial testing
2. **Monitor Resources**: Watch memory and disk usage
3. **Enable Cleanup**: Use `CLEANUP_IMAGES: true` for production
4. **Validate Parameters**: Check parameter formats before execution
5. **Archive Outputs**: Enable artifact archiving for important results
6. **Use Appropriate Tags**: Use `latest` for production, branch names for development
7. **Test Incrementally**: Test each application separately before running together

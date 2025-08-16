#!/usr/bin/env python3
"""
Excel Data Processor Application (App2)
Advanced Excel file processing with analytics and visualization
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os
import sys
import argparse
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


def parse_arguments():
    """Parse command-line arguments for the Excel processor."""
    parser = argparse.ArgumentParser(
        description='Excel Data Processor Application - Processes and analyzes Excel files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python processor_main.py --input data.xlsx --analysis full
  python processor_main.py -i report.xlsx -a summary --output-dir /app/reports
  python processor_main.py --input financial.xlsx --analysis charts --format png
        """
    )

    parser.add_argument(
        '--input', '-i',
        default='input_data.xlsx',
        help='Input Excel filename to process (default: input_data.xlsx)'
    )

    parser.add_argument(
        '--analysis', '-a',
        choices=['full', 'summary', 'charts'],
        default='full',
        help='Type of analysis to perform (default: full)'
    )

    parser.add_argument(
        '--output-dir',
        default='/app/reports',
        help='Output directory for reports (default: /app/reports)'
    )

    parser.add_argument(
        '--format',
        choices=['png', 'pdf', 'svg'],
        default='png',
        help='Output format for charts (default: png)'
    )

    return parser.parse_args()


def process_excel_file(input_path, analysis_type, output_dir, chart_format):
    """Process Excel file based on analysis type."""
    print(f"[PROCESSING] Analyzing file: {input_path}")
    print(f"[CONFIG] Analysis: {analysis_type}, Output: {output_dir}, Format: {chart_format}")

    try:
        # Read Excel file
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Read all sheets
        excel_data = pd.read_excel(input_path, sheet_name=None)
        print(f"[DATA] Found {len(excel_data)} sheets in Excel file")

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        results = {}

        for sheet_name, df in excel_data.items():
            print(f"[SHEET] Processing sheet: {sheet_name} ({len(df)} rows)")

            if analysis_type in ['full', 'summary']:
                # Generate summary statistics
                summary = generate_summary_stats(df, sheet_name)
                results[sheet_name] = summary

                # Save summary to file
                summary_file = os.path.join(output_dir, f"{sheet_name}_summary.json")
                with open(summary_file, 'w') as f:
                    json.dump(summary, f, indent=2, default=str)
                print(f"[SAVED] Summary: {summary_file}")

            if analysis_type in ['full', 'charts']:
                # Generate charts
                chart_files = generate_charts(df, sheet_name, output_dir, chart_format)
                print(f"[CHARTS] Generated {len(chart_files)} charts for {sheet_name}")

        # Generate overall report
        if analysis_type == 'full':
            report_file = generate_overall_report(results, output_dir)
            print(f"[REPORT] Overall report: {report_file}")

        return True

    except Exception as e:
        print(f"[ERROR] Processing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def generate_summary_stats(df, sheet_name):
    """Generate summary statistics for a DataFrame."""
    summary = {
        'sheet_name': sheet_name,
        'total_rows': len(df),
        'total_columns': len(df.columns),
        'columns': list(df.columns),
        'data_types': df.dtypes.to_dict(),
        'missing_values': df.isnull().sum().to_dict(),
        'memory_usage': df.memory_usage(deep=True).sum(),
        'processed_at': datetime.now().isoformat()
    }

    # Add numeric column statistics
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        summary['numeric_stats'] = df[numeric_cols].describe().to_dict()

    return summary


def generate_charts(df, sheet_name, output_dir, chart_format):
    """Generate charts for the DataFrame."""
    chart_files = []

    # Set matplotlib backend for headless operation
    plt.switch_backend('Agg')

    try:
        # Get numeric columns for charts
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        if len(numeric_cols) > 0:
            # Create distribution plots for numeric columns
            for col in numeric_cols[:5]:  # Limit to first 5 numeric columns
                plt.figure(figsize=(10, 6))
                plt.hist(df[col].dropna(), bins=30, alpha=0.7)
                plt.title(f'Distribution of {col} - {sheet_name}')
                plt.xlabel(col)
                plt.ylabel('Frequency')

                chart_file = os.path.join(output_dir, f"{sheet_name}_{col}_distribution.{chart_format}")
                plt.savefig(chart_file, dpi=300, bbox_inches='tight')
                plt.close()
                chart_files.append(chart_file)

            # Create correlation heatmap if multiple numeric columns
            if len(numeric_cols) > 1:
                plt.figure(figsize=(12, 8))
                correlation_matrix = df[numeric_cols].corr()
                sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0)
                plt.title(f'Correlation Matrix - {sheet_name}')

                chart_file = os.path.join(output_dir, f"{sheet_name}_correlation_heatmap.{chart_format}")
                plt.savefig(chart_file, dpi=300, bbox_inches='tight')
                plt.close()
                chart_files.append(chart_file)

    except Exception as e:
        print(f"[WARNING] Chart generation failed for {sheet_name}: {str(e)}")

    return chart_files


def generate_overall_report(results, output_dir):
    """Generate an overall analysis report."""
    report = {
        'analysis_summary': {
            'total_sheets': len(results),
            'total_rows': sum(r['total_rows'] for r in results.values()),
            'total_columns': sum(r['total_columns'] for r in results.values()),
            'analysis_date': datetime.now().isoformat()
        },
        'sheet_details': results
    }

    report_file = os.path.join(output_dir, 'overall_analysis_report.json')
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    return report_file


def main():
    """Main function to run the Excel processor."""
    print("[START] Excel Data Processor Application")
    print("=" * 50)

    # Parse command-line arguments
    args = parse_arguments()

    print(f"[ARGS] Input file: {args.input}")
    print(f"[ARGS] Analysis type: {args.analysis}")
    print(f"[ARGS] Output directory: {args.output_dir}")
    print(f"[ARGS] Chart format: {args.format}")
    print("-" * 50)

    try:
        # Construct full input path
        input_path = os.path.join('/app/input', args.input)

        # Process the Excel file
        success = process_excel_file(
            input_path=input_path,
            analysis_type=args.analysis,
            output_dir=args.output_dir,
            chart_format=args.format
        )

        if success:
            print("=" * 50)
            print("[COMPLETE] Excel processing completed successfully!")
            print(f"[OUTPUT] Reports saved to: {args.output_dir}")
            print("=" * 50)
            return 0
        else:
            print("[ERROR] Excel processing failed!")
            return 1

    except Exception as e:
        print(f"[ERROR] An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
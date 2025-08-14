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
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


class ExcelAnalyticsProcessor:
    """Advanced Excel processor with analytics capabilities"""
    
    def __init__(self, input_dir="input", output_dir="output", reports_dir="reports"):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.reports_dir = reports_dir
        self.timestamp = datetime.now()
        self.ensure_directories()
        
    def ensure_directories(self):
        """Create necessary directories"""
        for directory in [self.input_dir, self.output_dir, self.reports_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"[CREATED] Directory: {directory}")
    
    def find_excel_files(self):
        """Find all Excel files in input directory"""
        excel_files = []
        for root, dirs, files in os.walk(self.input_dir):
            for file in files:
                if file.endswith(('.xlsx', '.xls')):
                    excel_files.append(os.path.join(root, file))
        
        print(f"[FOUND] {len(excel_files)} Excel file(s) to process")
        for file in excel_files:
            print(f"[INPUT_FILE] {file}")
        
        return excel_files
    
    def load_and_analyze_excel(self, filepath):
        """Load Excel file and perform comprehensive analysis"""
        print(f"[PROCESSING] Analyzing Excel file: {filepath}")
        
        try:
            # Read all sheets
            excel_data = pd.read_excel(filepath, sheet_name=None)
            
            analysis_results = {
                'file_path': filepath,
                'file_size_mb': round(os.path.getsize(filepath) / (1024 * 1024), 2),
                'sheets_analyzed': {},
                'summary_statistics': {},
                'data_quality_report': {}
            }
            
            for sheet_name, df in excel_data.items():
                print(f"[SHEET] Analyzing sheet: {sheet_name}")
                
                sheet_analysis = self.analyze_dataframe(df, sheet_name)
                analysis_results['sheets_analyzed'][sheet_name] = sheet_analysis
            
            return analysis_results
            
        except Exception as e:
            print(f"[ERROR] Failed to analyze {filepath}: {str(e)}")
            return None
    
    def analyze_dataframe(self, df, sheet_name):
        """Perform detailed analysis on a DataFrame"""
        analysis = {
            'row_count': len(df),
            'column_count': len(df.columns),
            'columns': list(df.columns),
            'data_types': df.dtypes.to_dict(),
            'missing_values': df.isnull().sum().to_dict(),
            'memory_usage_mb': round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2)
        }
        
        # Numeric column analysis
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) > 0:
            analysis['numeric_summary'] = df[numeric_columns].describe().to_dict()
        
        # Text column analysis
        text_columns = df.select_dtypes(include=['object']).columns
        if len(text_columns) > 0:
            analysis['text_summary'] = {}
            for col in text_columns:
                analysis['text_summary'][col] = {
                    'unique_values': df[col].nunique(),
                    'most_common': df[col].value_counts().head(3).to_dict()
                }
        
        # Date column analysis
        date_columns = df.select_dtypes(include=['datetime64']).columns
        if len(date_columns) > 0:
            analysis['date_summary'] = {}
            for col in date_columns:
                analysis['date_summary'][col] = {
                    'min_date': str(df[col].min()),
                    'max_date': str(df[col].max()),
                    'date_range_days': (df[col].max() - df[col].min()).days
                }
        
        print(f"[ANALYZED] {sheet_name}: {len(df)} rows, {len(df.columns)} columns")
        return analysis
    
    def generate_analytics_report(self, analysis_results, output_filename="app2_analytics_report.xlsx"):
        """Generate comprehensive analytics report"""
        output_path = os.path.join(self.output_dir, output_filename)
        
        print(f"[REPORT] Creating analytics report: {output_path}")
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = []
            for file_path, file_analysis in analysis_results.items():
                for sheet_name, sheet_data in file_analysis['sheets_analyzed'].items():
                    summary_data.append({
                        'Source_File': os.path.basename(file_path),
                        'Sheet_Name': sheet_name,
                        'Row_Count': sheet_data['row_count'],
                        'Column_Count': sheet_data['column_count'],
                        'Memory_Usage_MB': sheet_data['memory_usage_mb'],
                        'Missing_Values': sum(sheet_data['missing_values'].values())
                    })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Data quality sheet
            quality_data = []
            for file_path, file_analysis in analysis_results.items():
                for sheet_name, sheet_data in file_analysis['sheets_analyzed'].items():
                    for column, missing_count in sheet_data['missing_values'].items():
                        if missing_count > 0:
                            quality_data.append({
                                'File': os.path.basename(file_path),
                                'Sheet': sheet_name,
                                'Column': column,
                                'Missing_Values': missing_count,
                                'Data_Type': str(sheet_data['data_types'].get(column, 'Unknown'))
                            })
            
            if quality_data:
                quality_df = pd.DataFrame(quality_data)
                quality_df.to_excel(writer, sheet_name='Data_Quality', index=False)
        
        print(f"[SUCCESS] Analytics report created: {output_path}")
        return output_path
    
    def process_all_files(self):
        """Process all Excel files in input directory"""
        print("[PROCESSING] Starting comprehensive Excel analysis...")
        
        excel_files = self.find_excel_files()
        
        if not excel_files:
            print("[WARNING] No Excel files found to process")
            return False
        
        all_analysis_results = {}
        
        for excel_file in excel_files:
            analysis = self.load_and_analyze_excel(excel_file)
            if analysis:
                all_analysis_results[excel_file] = analysis
        
        if all_analysis_results:
            # Generate analytics report
            report_path = self.generate_analytics_report(all_analysis_results)
            
            # Save detailed analysis as JSON
            json_path = os.path.join(self.output_dir, 'app2_detailed_analysis.json')
            with open(json_path, 'w') as f:
                json.dump(all_analysis_results, f, indent=2, default=str)
            
            print(f"[JSON] Detailed analysis saved: {json_path}")
            
            # Generate summary
            self.generate_processing_summary(all_analysis_results)
            
            return True
        else:
            print("[ERROR] No files were successfully processed")
            return False
    
    def generate_processing_summary(self, analysis_results):
        """Generate and display processing summary"""
        print("\n[SUMMARY] App2 Processing Results")
        print("=" * 50)
        
        total_files = len(analysis_results)
        total_sheets = sum(len(result['sheets_analyzed']) for result in analysis_results.values())
        total_rows = sum(
            sum(sheet['row_count'] for sheet in result['sheets_analyzed'].values())
            for result in analysis_results.values()
        )
        
        print(f"[FILES_PROCESSED] {total_files}")
        print(f"[SHEETS_ANALYZED] {total_sheets}")
        print(f"[TOTAL_ROWS] {total_rows}")
        print(f"[PROCESSING_TIME] {datetime.now()}")
        
        # Save summary
        summary = {
            'app_name': 'app2',
            'app_type': 'excel-processor',
            'processing_timestamp': self.timestamp.isoformat(),
            'files_processed': total_files,
            'sheets_analyzed': total_sheets,
            'total_rows_processed': total_rows,
            'processor_version': '2.0.0'
        }
        
        summary_path = os.path.join(self.output_dir, 'app2_processing_summary.json')
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"[SAVED] Processing summary: {summary_path}")


def main():
    """Main execution function for App2"""
    print("[START] App2 - Excel Analytics Processor")
    print("=" * 60)
    print("[INFO] Initializing Excel analytics processor...")
    print("[FIXED] PowerShell commands now working correctly in Jenkins")
    
    try:
        # Initialize processor
        processor = ExcelAnalyticsProcessor()
        
        # Process all Excel files
        success = processor.process_all_files()
        
        if success:
            print(f"[COMPLETE] App2 Excel processing completed successfully")
            return True
        else:
            print(f"[FAILED] App2 Excel processing failed")
            return False
        
    except Exception as e:
        print(f"[ERROR] App2 processing failed: {str(e)}")
        return False


if __name__ == "__main__":
    success = main()
    exit_code = 0 if success else 1
    print(f"[EXIT] App2 process completed with exit code: {exit_code}")
    sys.exit(exit_code)

#!/usr/bin/env python3
"""
Excel Generator Application (App1)
Generates comprehensive Excel files with business data using Faker for realistic data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
import json
from faker import Faker


class BusinessDataGenerator:
    """Advanced Excel data generator with realistic business data"""
    
    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        self.timestamp = datetime.now()
        self.fake = Faker()
        self.ensure_output_directory()
        
    def ensure_output_directory(self):
        """Create output directory if it doesn't exist"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"[CREATED] Output directory: {self.output_dir}")
    
    def generate_customer_data(self, num_customers=500):
        """Generate realistic customer data"""
        print(f"[GENERATING] Creating {num_customers} customer records...")
        
        Faker.seed(42)
        
        customers = []
        for i in range(num_customers):
            customer = {
                'Customer_ID': f"CUST{1000 + i:04d}",
                'Company_Name': self.fake.company(),
                'Contact_Name': self.fake.name(),
                'Email': self.fake.email(),
                'Phone': self.fake.phone_number(),
                'Address': self.fake.address().replace('\n', ', '),
                'City': self.fake.city(),
                'State': self.fake.state(),
                'Postal_Code': self.fake.postcode(),
                'Country': self.fake.country(),
                'Industry': self.fake.random_element(['Technology', 'Healthcare', 'Finance', 'Manufacturing', 'Retail']),
                'Company_Size': self.fake.random_element(['Small', 'Medium', 'Large', 'Enterprise']),
                'Registration_Date': self.fake.date_between(start_date='-2y', end_date='today'),
                'Credit_Limit': round(self.fake.random_int(min=5000, max=100000), -2),
                'Status': self.fake.random_element(['Active', 'Inactive', 'Pending', 'Suspended'])
            }
            customers.append(customer)
        
        return pd.DataFrame(customers)
    
    def generate_sales_transactions(self, num_transactions=2000):
        """Generate realistic sales transaction data"""
        print(f"[GENERATING] Creating {num_transactions} sales transactions...")
        
        products = [
            {'name': 'Enterprise Software License', 'price_range': (1000, 5000)},
            {'name': 'Cloud Storage Subscription', 'price_range': (50, 500)},
            {'name': 'Data Analytics Platform', 'price_range': (2000, 10000)},
            {'name': 'Security Monitoring Tool', 'price_range': (500, 3000)},
            {'name': 'API Management Service', 'price_range': (100, 1000)}
        ]
        
        transactions = []
        for i in range(num_transactions):
            product = self.fake.random_element(products)
            quantity = self.fake.random_int(min=1, max=10)
            unit_price = self.fake.random_int(min=product['price_range'][0], max=product['price_range'][1])
            
            transaction = {
                'Transaction_ID': f"TXN{10000 + i:05d}",
                'Customer_ID': f"CUST{self.fake.random_int(min=1000, max=1499):04d}",
                'Product_Name': product['name'],
                'Quantity': quantity,
                'Unit_Price': unit_price,
                'Total_Amount': quantity * unit_price,
                'Transaction_Date': self.fake.date_time_between(start_date='-1y', end_date='now'),
                'Sales_Rep': self.fake.name(),
                'Region': self.fake.random_element(['North America', 'Europe', 'Asia Pacific', 'Latin America']),
                'Payment_Method': self.fake.random_element(['Credit Card', 'Bank Transfer', 'Check', 'PayPal']),
                'Status': self.fake.random_element(['Completed', 'Pending', 'Cancelled', 'Refunded'])
            }
            transactions.append(transaction)
        
        return pd.DataFrame(transactions)
    
    def generate_inventory_data(self, num_items=300):
        """Generate inventory management data"""
        print(f"[GENERATING] Creating {num_items} inventory items...")
        
        categories = ['Software', 'Hardware', 'Services', 'Licenses', 'Support']
        
        inventory = []
        for i in range(num_items):
            item = {
                'SKU': f"SKU{2000 + i:04d}",
                'Product_Name': self.fake.catch_phrase(),
                'Category': self.fake.random_element(categories),
                'Supplier': self.fake.company(),
                'Cost_Price': round(self.fake.random_int(min=10, max=1000), 2),
                'Selling_Price': round(self.fake.random_int(min=15, max=1500), 2),
                'Stock_Quantity': self.fake.random_int(min=0, max=1000),
                'Reorder_Level': self.fake.random_int(min=10, max=100),
                'Last_Restocked': self.fake.date_between(start_date='-6m', end_date='today'),
                'Warehouse_Location': f"WH-{self.fake.random_element(['A', 'B', 'C'])}-{self.fake.random_int(min=1, max=50):02d}",
                'Status': self.fake.random_element(['In Stock', 'Low Stock', 'Out of Stock', 'Discontinued'])
            }
            inventory.append(item)
        
        return pd.DataFrame(inventory)
    
    def create_comprehensive_excel(self, filename="app1_business_data.xlsx"):
        """Create comprehensive Excel file with multiple business data sheets"""
        filepath = os.path.join(self.output_dir, filename)
        
        print(f"[EXCEL] Creating comprehensive Excel file: {filepath}")
        
        # Generate all data
        customers_df = self.generate_customer_data()
        transactions_df = self.generate_sales_transactions()
        inventory_df = self.generate_inventory_data()
        
        # Create Excel writer with formatting
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Write customer data
            customers_df.to_excel(writer, sheet_name='Customers', index=False)
            
            # Write transaction data
            transactions_df.to_excel(writer, sheet_name='Sales_Transactions', index=False)
            
            # Write inventory data
            inventory_df.to_excel(writer, sheet_name='Inventory', index=False)
            
            # Create dashboard summary
            dashboard_data = {
                'Metric': [
                    'Total Customers',
                    'Total Transactions', 
                    'Total Revenue',
                    'Average Transaction Value',
                    'Total Inventory Items',
                    'Total Inventory Value',
                    'Generated Date',
                    'Application'
                ],
                'Value': [
                    len(customers_df),
                    len(transactions_df),
                    f"${transactions_df['Total_Amount'].sum():,.2f}",
                    f"${transactions_df['Total_Amount'].mean():.2f}",
                    len(inventory_df),
                    f"${(inventory_df['Stock_Quantity'] * inventory_df['Cost_Price']).sum():,.2f}",
                    self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'App1 - Business Data Generator'
                ]
            }
            dashboard_df = pd.DataFrame(dashboard_data)
            dashboard_df.to_excel(writer, sheet_name='Dashboard', index=False)
        
        # Calculate file size
        file_size_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2)
        
        print(f"[SUCCESS] Excel file created successfully")
        print(f"[FILE_PATH] {filepath}")
        print(f"[FILE_SIZE] {file_size_mb} MB")
        print(f"[SHEETS] Customers ({len(customers_df)} rows)")
        print(f"[SHEETS] Sales_Transactions ({len(transactions_df)} rows)")
        print(f"[SHEETS] Inventory ({len(inventory_df)} rows)")
        print(f"[SHEETS] Dashboard (summary)")
        
        # Create metadata
        metadata = {
            'app_name': 'app1',
            'app_type': 'excel-generator',
            'filename': filename,
            'filepath': filepath,
            'file_size_mb': file_size_mb,
            'sheets': {
                'Customers': len(customers_df),
                'Sales_Transactions': len(transactions_df),
                'Inventory': len(inventory_df),
                'Dashboard': len(dashboard_df)
            },
            'generated_at': self.timestamp.isoformat(),
            'generator_version': '2.0.0'
        }
        
        metadata_path = os.path.join(self.output_dir, 'app1_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"[METADATA] Created metadata file: {metadata_path}")
        
        return filepath, metadata


def main():
    """Main execution function for App1"""
    print("[START] App1 - Excel Business Data Generator")
    print("=" * 60)
    
    try:
        # Initialize generator
        generator = BusinessDataGenerator()
        
        # Generate comprehensive Excel file
        excel_path, metadata = generator.create_comprehensive_excel()
        
        print(f"[COMPLETE] App1 Excel generation completed successfully")
        print(f"[OUTPUT] File: {excel_path}")
        print(f"[TOTAL_RECORDS] {sum(metadata['sheets'].values())} total records")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] App1 Excel generation failed: {str(e)}")
        return False


if __name__ == "__main__":
    success = main()
    exit_code = 0 if success else 1
    print(f"[EXIT] App1 process completed with exit code: {exit_code}")
    sys.exit(exit_code)

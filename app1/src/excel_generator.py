#!/usr/bin/env python3
"""
Excel Generator Application (App1)  Test Test
Generates comprehensive Excel files with business data using Faker for realistic data
"""

import pandas as pd
import os
import sys
import argparse
from faker import Faker


def parse_arguments():
    """Parse command-line arguments for the Excel generator."""
    parser = argparse.ArgumentParser(
        description='Excel Generator Application - Creates comprehensive Excel files with business data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python excel_generator.py --output report.xlsx --records 1000
  python excel_generator.py -o financial_data.xlsx -r 5000 -f financial -s 3
  python excel_generator.py --format customer --sheets 2 --records 2500
        """
    )

    parser.add_argument(
        '--output', '-o',
        default='generated_data.xlsx',
        help='Output Excel filename (default: generated_data.xlsx)'
    )

    parser.add_argument(
        '--records', '-r',
        type=int,
        default=1000,
        help='Number of records to generate per sheet (default: 1000)'
    )

    parser.add_argument(
        '--format', '-f',
        choices=['business', 'financial', 'customer'],
        default='business',
        help='Data format type to generate (default: business)'
    )

    parser.add_argument(
        '--sheets', '-s',
        type=int,
        default=1,
        help='Number of Excel sheets to create (default: 1)'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducible data generation (default: 42)'
    )

    return parser.parse_args()


def generate_business_data(fake, num_records):
    """Generate business-related data."""
    print(f"[DATA] Generating {num_records} business records...")

    data = []
    for i in range(num_records):
        record = {
            'ID': i + 1,
            'Company': fake.company(),
            'Contact_Name': fake.name(),
            'Email': fake.email(),
            'Phone': fake.phone_number(),
            'Address': fake.address().replace('\n', ', '),
            'City': fake.city(),
            'State': fake.state(),
            'ZIP': fake.zipcode(),
            'Country': fake.country(),
            'Industry': fake.random_element(['Technology', 'Healthcare', 'Finance', 'Manufacturing', 'Retail', 'Education']),
            'Revenue': fake.random_int(min=10000, max=10000000),
            'Employees': fake.random_int(min=1, max=5000),
            'Founded': fake.date_between(start_date='-50y', end_date='-1y'),
            'Website': fake.url(),
            'Description': fake.text(max_nb_chars=200),
            'Last_Contact': fake.date_between(start_date='-1y', end_date='today'),
            'Status': fake.random_element(['Active', 'Inactive', 'Pending', 'Prospect'])
        }
        data.append(record)

    return pd.DataFrame(data)


def generate_financial_data(fake, num_records):
    """Generate financial-related data."""
    print(f"[DATA] Generating {num_records} financial records...")

    data = []
    for i in range(num_records):
        record = {
            'Transaction_ID': f"TXN-{i+1:06d}",
            'Date': fake.date_between(start_date='-2y', end_date='today'),
            'Account_Number': fake.random_int(min=1000000000, max=9999999999),
            'Account_Name': fake.name(),
            'Transaction_Type': fake.random_element(['Deposit', 'Withdrawal', 'Transfer', 'Payment', 'Fee']),
            'Amount': round(fake.random.uniform(-10000, 50000), 2),
            'Balance': round(fake.random.uniform(0, 100000), 2),
            'Currency': fake.random_element(['USD', 'EUR', 'GBP', 'JPY', 'CAD']),
            'Description': fake.sentence(nb_words=6),
            'Category': fake.random_element(['Business', 'Personal', 'Investment', 'Loan', 'Credit Card']),
            'Branch': fake.city(),
            'Reference': fake.uuid4(),
            'Status': fake.random_element(['Completed', 'Pending', 'Failed', 'Cancelled']),
            'Fee': round(fake.random.uniform(0, 25), 2) if fake.boolean(chance_of_getting_true=30) else 0
        }
        data.append(record)

    return pd.DataFrame(data)


def generate_customer_data(fake, num_records):
    """Generate customer-related data."""
    print(f"[DATA] Generating {num_records} customer records...")

    data = []
    for i in range(num_records):
        record = {
            'Customer_ID': f"CUST-{i+1:05d}",
            'First_Name': fake.first_name(),
            'Last_Name': fake.last_name(),
            'Email': fake.email(),
            'Phone': fake.phone_number(),
            'Date_of_Birth': fake.date_of_birth(minimum_age=18, maximum_age=80),
            'Gender': fake.random_element(['Male', 'Female', 'Other']),
            'Address': fake.street_address(),
            'City': fake.city(),
            'State': fake.state(),
            'ZIP': fake.zipcode(),
            'Country': fake.country(),
            'Registration_Date': fake.date_between(start_date='-3y', end_date='today'),
            'Last_Login': fake.date_between(start_date='-30d', end_date='today'),
            'Total_Orders': fake.random_int(min=0, max=100),
            'Total_Spent': round(fake.random.uniform(0, 5000), 2),
            'Preferred_Category': fake.random_element(['Electronics', 'Clothing', 'Books', 'Home & Garden', 'Sports']),
            'Loyalty_Points': fake.random_int(min=0, max=10000),
            'Status': fake.random_element(['Active', 'Inactive', 'VIP', 'Suspended']),
            'Marketing_Consent': fake.boolean()
        }
        data.append(record)

    return pd.DataFrame(data)


def create_excel_file(output_path, data_format, num_records, num_sheets, seed):
    """Create Excel file with specified parameters."""
    print(f"[EXCEL] Creating Excel file: {output_path}")
    print(f"[CONFIG] Format: {data_format}, Records: {num_records}, Sheets: {num_sheets}, Seed: {seed}")

    # Initialize Faker with seed for reproducible data
    fake = Faker()
    fake.seed_instance(seed)

    # Create Excel writer
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for sheet_num in range(num_sheets):
            sheet_name = f"{data_format.title()}_Data_{sheet_num + 1}"

            print(f"[SHEET] Creating sheet {sheet_num + 1}/{num_sheets}: {sheet_name}")

            # Generate data based on format
            if data_format == 'business':
                df = generate_business_data(fake, num_records)
            elif data_format == 'financial':
                df = generate_financial_data(fake, num_records)
            elif data_format == 'customer':
                df = generate_customer_data(fake, num_records)
            else:
                raise ValueError(f"Unknown data format: {data_format}")

            # Write to Excel sheet
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Get the worksheet to apply formatting
            worksheet = writer.sheets[sheet_name]

            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                worksheet.column_dimensions[column_letter].width = adjusted_width

    print(f"[SUCCESS] Excel file created successfully: {output_path}")
    return True


def main():
    """Main function to run the Excel generator."""
    print("[START] Excel Generator Application")
    print("=" * 50)

    # Parse command-line arguments
    args = parse_arguments()

    print(f"[ARGS] Output file: {args.output}")
    print(f"[ARGS] Records per sheet: {args.records}")
    print(f"[ARGS] Data format: {args.format}")
    print(f"[ARGS] Number of sheets: {args.sheets}")
    print(f"[ARGS] Random seed: {args.seed}")
    print("-" * 50)

    try:
        # Ensure output directory exists
        output_dir = '/app/output'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"[SETUP] Created output directory: {output_dir}")

        # Full path for output file
        output_path = os.path.join(output_dir, args.output)

        # Generate Excel file
        success = create_excel_file(
            output_path=output_path,
            data_format=args.format,
            num_records=args.records,
            num_sheets=args.sheets,
            seed=args.seed
        )

        if success:
            # Get file size for reporting
            file_size = os.path.getsize(output_path)
            file_size_mb = file_size / (1024 * 1024)

            print("=" * 50)
            print("[COMPLETE] Excel generation completed successfully!")
            print(f"[OUTPUT] File: {output_path}")
            print(f"[SIZE] File size: {file_size_mb:.2f} MB")
            print(f"[STATS] Total records: {args.records * args.sheets:,}")
            print(f"[STATS] Sheets created: {args.sheets}")
            print("=" * 50)

            return 0
        else:
            print("[ERROR] Excel generation failed!")
            return 1

    except Exception as e:
        print(f"[ERROR] An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
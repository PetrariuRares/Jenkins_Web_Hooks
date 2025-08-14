#!/usr/bin/env python3
"""
Test suite for App1 Excel Generator Test Test
"""

import unittest
import sys
import os
import tempfile
import pandas as pd

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from excel_generator import BusinessDataGenerator
except ImportError:
    print("[ERROR] Could not import excel_generator module")
    BusinessDataGenerator = None


class TestBusinessDataGenerator(unittest.TestCase):
    """Test cases for BusinessDataGenerator class"""
    
    def setUp(self):
        """Set up test fixtures"""
        if BusinessDataGenerator:
            self.temp_dir = tempfile.mkdtemp()
            self.generator = BusinessDataGenerator(output_dir=self.temp_dir)
    
    def test_customer_data_generation(self):
        """Test customer data generation"""
        if not BusinessDataGenerator:
            self.skipTest("BusinessDataGenerator not available")
        
        customers_df = self.generator.generate_customer_data(num_customers=10)
        
        self.assertEqual(len(customers_df), 10)
        self.assertIn('Customer_ID', customers_df.columns)
        self.assertIn('Company_Name', customers_df.columns)
        self.assertIn('Email', customers_df.columns)
        
        print("[TEST_PASS] Customer data generation test passed")
    
    def test_sales_transaction_generation(self):
        """Test sales transaction data generation"""
        if not BusinessDataGenerator:
            self.skipTest("BusinessDataGenerator not available")
        
        transactions_df = self.generator.generate_sales_transactions(num_transactions=20)
        
        self.assertEqual(len(transactions_df), 20)
        self.assertIn('Transaction_ID', transactions_df.columns)
        self.assertIn('Total_Amount', transactions_df.columns)
        
        # Verify calculated totals
        for _, row in transactions_df.iterrows():
            expected_total = row['Quantity'] * row['Unit_Price']
            self.assertEqual(row['Total_Amount'], expected_total)
        
        print("[TEST_PASS] Sales transaction generation test passed")
    
    def test_inventory_data_generation(self):
        """Test inventory data generation"""
        if not BusinessDataGenerator:
            self.skipTest("BusinessDataGenerator not available")
        
        inventory_df = self.generator.generate_inventory_data(num_items=15)
        
        self.assertEqual(len(inventory_df), 15)
        self.assertIn('SKU', inventory_df.columns)
        self.assertIn('Stock_Quantity', inventory_df.columns)
        
        print("[TEST_PASS] Inventory data generation test passed")
    
    def test_excel_file_creation(self):
        """Test complete Excel file creation"""
        if not BusinessDataGenerator:
            self.skipTest("BusinessDataGenerator not available")
        
        filepath, metadata = self.generator.create_comprehensive_excel("test_output.xlsx")
        
        # Verify file exists
        self.assertTrue(os.path.exists(filepath))
        
        # Verify metadata
        self.assertIn('app_name', metadata)
        self.assertEqual(metadata['app_name'], 'app1')
        self.assertIn('sheets', metadata)
        
        # Verify Excel file can be read
        excel_data = pd.read_excel(filepath, sheet_name=None)
        expected_sheets = ['Customers', 'Sales_Transactions', 'Inventory', 'Dashboard']
        
        for sheet in expected_sheets:
            self.assertIn(sheet, excel_data.keys())
        
        print("[TEST_PASS] Excel file creation test passed")


def run_app1_tests():
    """Run all App1 tests"""
    print("[START] App1 Test Suite")
    print("=" * 40)
    
    if not BusinessDataGenerator:
        print("[ERROR] Cannot run tests - excel_generator module not found")
        return False
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestBusinessDataGenerator)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Display summary
    print("\n[SUMMARY] App1 Test Results")
    print(f"[TESTS_RUN] {result.testsRun}")
    print(f"[FAILURES] {len(result.failures)}")
    print(f"[ERRORS] {len(result.errors)}")
    
    if result.wasSuccessful():
        print("[SUCCESS] All App1 tests passed!")
        return True
    else:
        print("[FAILURE] Some App1 tests failed!")
        for failure in result.failures:
            print(f"[FAIL_DETAIL] {failure[0]}: {failure[1]}")
        for error in result.errors:
            print(f"[ERROR_DETAIL] {error[0]}: {error[1]}")
        return False


if __name__ == "__main__":
    success = run_app1_tests()
    exit_code = 0 if success else 1
    print(f"[EXIT] App1 tests completed with exit code: {exit_code}")
    sys.exit(exit_code)

import pandas as pd
from google.cloud import bigquery
import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime

def assign_awards_sequentially():
    """Main function to assign awards using cascading logic"""

    # Initialize BigQuery client with proper credentials handling
    try:
        if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            # GitHub Actions environment - use default credentials
            from google.auth import default
            credentials, project = default()
            client = bigquery.Client(credentials=credentials, project=project)
        else:
            # Local environment - use service account file
            client = bigquery.Client()
    except Exception as e:
        print(f"Error initializing BigQuery client: {e}")
        # Fallback to default initialization
        client = bigquery.Client()

    # 1. Read awards config directly from Google Sheets
    awards_config = read_awards_config_from_sheet()

    # 2. Read product data from BigQuery
    try:
        products_query = """
        SELECT * FROM `reporting-446813.har_marts.rep_sku_scores`
        WHERE product_id IS NOT NULL
        """
        products = client.query(products_query).to_dataframe()
        print(f"Retrieved {len(products)} products from BigQuery")
    except Exception as e:
        print(f"Error querying BigQuery: {e}")
        raise

    # 3. Sequential assignment logic
    used_products = set()
    assigned_awards = []

    # Step 1: Process ALL manual awards first (regardless of priority)
    print("Processing manual awards first...")
    for _, award in awards_config.iterrows():
        # Check if overwrite_product_id has a value (manual award)
        if pd.notna(award.get('overwrite_product_id')) and award['overwrite_product_id']:
            # Find the corresponding parent_msku for this product_id
            product_info = products[products['product_id'] == award['overwrite_product_id']]
            if len(product_info) > 0:
                parent_msku = product_info.iloc[0]['parent_msku']
                assigned_awards.append({
                    'product_id': award['overwrite_product_id'],
                    'parent_msku': parent_msku,
                    'award_text': award['award'],
                    'priority': award['priority'],
                    'category': award['category'],
                    'metric': award['metric'],
                    'is_manual': True,
                    'assigned_at': datetime.now()
                })
                used_products.add(award['overwrite_product_id'])
            else:
                print(f"Warning: Product ID {award['overwrite_product_id']} not found in product data for award {award['award']}")

    # Step 2: Process dynamic awards in priority order
    print("Processing dynamic awards in priority order...")
    for _, award in awards_config.iterrows():
        # Skip manual awards (already processed)
        if pd.notna(award.get('overwrite_product_id')) and award['overwrite_product_id']:
            continue

        # Get eligible products
        eligible_products = get_eligible_products(products, award, used_products)

        if len(eligible_products) > 0:
            # Map metric name to actual column name
            metric_column = get_metric_column_name(award['metric'])
            best_product = eligible_products.nlargest(1, metric_column).iloc[0]

            assigned_awards.append({
                'product_id': best_product['product_id'],
                'parent_msku': best_product['parent_msku'],
                'award_text': award['award'],
                'priority': award['priority'],
                'category': award['category'],
                'metric': award['metric'],
                'is_manual': False,
                'assigned_at': datetime.now()
            })

            used_products.add(best_product['product_id'])
        else:
            print(f"No eligible products for award: {award['award']}")

    # 4. Write results back to BigQuery
    if assigned_awards:
        df = pd.DataFrame(assigned_awards)

        # Write to BigQuery
        table_id = "reporting-446813.har_marts.fct_assigned_awards"
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE  # Replace table
        )

        job = client.load_table_from_dataframe(
            df, table_id, job_config=job_config
        )
        job.result()  # Wait for job to complete

        # Also save to local CSV for inspection
        # csv_path = "assigned_awards.csv"
        # df.to_csv(csv_path, index=False)
        print(f"Successfully assigned {len(assigned_awards)} awards")
        # print(f"Results also saved to: {csv_path}")

def get_eligible_products(products, award, used_products):
    """Filter products eligible for this award"""

    # Basic filtering
    mask = ~products['product_id'].isin(used_products)

    # Category matching
    if award.get('strength'):
        mask &= products['tw_strength'] == award['strength']

    if award.get('flavour'):
        mask &= products['tw_flavour'] == award['flavour']

    # Competition flag checks
    if award.get('required_compete_flag'):
        flag_value = products.get(award['required_compete_flag'])
        if award['required_compete_flag'] == 'compete_flavour':
            # Default: compete unless explicitly set to false
            mask &= (flag_value.isna() | (flag_value != 'false'))
        else:
            # Other flags: require explicit 'true'
            mask &= (flag_value == 'true')

    return products[mask]

def read_awards_config_from_sheet():
    """Read awards config directly from Google Sheets"""

    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']

    try:
        # Debug: Print environment information
        sheets_sa_key = os.getenv('SHEETS_SA_KEY')
        gcp_credentials = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        print(f"Environment check: SHEETS_SA_KEY={'SET' if sheets_sa_key else 'NOT_SET'}, GOOGLE_APPLICATION_CREDENTIALS={'SET' if gcp_credentials else 'NOT_SET'}")

        # Check if running in GitHub Actions (credentials via environment variable)
        if sheets_sa_key:
            # GitHub Actions environment - use SHEETS_SA_KEY
            import json
            print("Using SHEETS_SA_KEY for Google Sheets authentication")
            sa_key_json = json.loads(sheets_sa_key)
            creds = Credentials.from_service_account_info(sa_key_json, scopes=scope)

        elif gcp_credentials:
            # GitHub Actions environment - use default credentials but for sheets
            print("Using GOOGLE_APPLICATION_CREDENTIALS for Google Sheets authentication")
            from google.auth import default
            creds, _ = default(scopes=scope)
        else:
            # Local environment - use service account file
            print("Using local service account file for Google Sheets authentication")
            if not os.path.exists('config/service_account.json'):
                raise FileNotFoundError("Service account file 'config/service_account.json' not found. Are you running this locally?")
            creds = Credentials.from_service_account_file(
                'config/service_account.json', scopes=scope)

        # Open the sheet
        client = gspread.authorize(creds)
        sheet = client.open_by_key('1jhcFaYHNxsDFgHx0dstacbBbkU_-bI-PVtuXcXqIqGk').worksheet('Input')

    except (gspread.exceptions.APIError, PermissionError, FileNotFoundError) as e:
        print("❌ Permission denied accessing Google Sheets")
        print("Underlying error:", str(e))
        if "Google Sheets API has not been used" in str(e):
            print("\n🔧 SOLUTION: Enable Google Sheets API")
            print("Visit: https://console.developers.google.com/apis/api/sheets.googleapis.com/overview")
            print("Then wait a few minutes for changes to propagate.")
        elif "Permission denied" in str(e):
            print("\n🔧 SOLUTION: Use separate service account for Google Sheets")
            print("Create config/service_account_sheets.json with Google Sheets API access")
        elif isinstance(e, FileNotFoundError):
            print("\n🔧 SOLUTION: Missing service account file")
            print("Make sure config/service_account.json exists for local development")
        raise

    # Read to pandas
    df = pd.DataFrame(sheet.get_all_records())

    print(f"Raw data from sheet: {len(df)} rows")
    print(f"Columns: {list(df.columns)}")

    # Filter active awards and sort by priority
    if 'active' in df.columns:
        # Handle both boolean True and string "TRUE"
        df = df[df['active'].str.upper() == 'TRUE'].sort_values('priority')
        print(f"After filtering active=TRUE: {len(df)} rows")
    else:
        print("Warning: No 'active' column found, using all rows")
        df = df.sort_values('priority')

    print(f"Final awards config: {len(df)} rows")
    return df
def get_metric_column_name(metric_name):
    """Map metric names from awards config to actual column names in product data"""
    metric_mapping = {
        'Best Selling (All Time)': 'total_quantity',
        'Best Rated': 'metacritic_score',
        'Best Momentum': 'weighted_growth_momentum',
        'Best Rated (90 days)': 'metacritic_score',
        'Bestselling': 'l90_quantity',
        'Best Selling (30 days)': 'l30_quantity',
        'Best Selling (14 days)': 'l14_quantity'
    }
    return metric_mapping.get(metric_name, metric_name)

if __name__ == "__main__":
    assign_awards_sequentially()
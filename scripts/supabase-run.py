import os
from supabase import create_client, Client
from dotenv import load_dotenv

def main():
    """
    Connects to Supabase and executes all SQL files in the output directory.
    """
    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_KEY must be set in your .env file.")
        return

    print("Connecting to Supabase...")
    supabase: Client = create_client(supabase_url, supabase_key)
    print("Successfully connected to Supabase.")

    output_dir = "../output"
    if not os.path.isdir(output_dir):
        print(f"Output directory '{output_dir}' not found. Please generate the SQL files first.")
        return

    sql_files = [f for f in os.listdir(output_dir) if f.endswith(".sql")]
    if not sql_files:
        print(f"No .sql files found in the '{output_dir}' directory.")
        return

    print(f"Found {len(sql_files)} SQL files to execute.")

    for filename in sorted(sql_files):
        file_path = os.path.join(output_dir, filename)
        print(f"\nExecuting {filename}...")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                sql_content = f.read()
            
            # Supabase Python library doesn't have a direct way to execute raw SQL 
            # that isn't a function. We need to create an RPC function.
            # The user will need to create a function in their Supabase SQL editor:
            # CREATE OR REPLACE FUNCTION execute_sql(sql TEXT) RETURNS void AS $
            # BEGIN
            #   EXECUTE sql;
            # END;
            # $ LANGUAGE plpgsql;
            supabase.rpc('execute_sql', {'sql': sql_content}).execute()
            print(f"Successfully executed {filename}.")

        except Exception as e:
            print(f"An error occurred while executing {filename}: {e}")

if __name__ == "__main__":
    main()

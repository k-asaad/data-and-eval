import os
from supabase import create_client, Client
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# --- Initialize Client ---
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Error initializing Supabase client: {e}")
    exit()

def get_data(table_name, **kwargs):
    """Fetches data from a Supabase table with optional filters."""
    try:
        query = supabase.table(table_name).select("*")
        for key, value in kwargs.items():
            query = query.eq(key, value)
        response = query.execute()
        return response.data
    except Exception as e:
        print(f"Error fetching data from {table_name}: {e}")
        return []

def run_check():
    """Runs the diagnostic check for Class 8 Arts."""
    print("--- Starting Data Integrity Check for Class 8 Arts ---")

    # 1. Find the Subject
    print("\n1. Searching for Subject...")
    subjects = get_data("subjects", class_name='8', subject_name='Arts')
    if not subjects:
        print("   - FAILED: Could not find a subject with class_name='8' AND subject_name='Arts'.")
        print("   - Please check your `subjects` table for the correct names.")
        return
    subject = subjects[0]
    subject_id = subject['id']
    print(f"   - SUCCESS: Found Subject '{subject['subject_name']}' (ID: {subject_id})")

    # 2. Find the Book
    print("\n2. Searching for associated Book...")
    books = get_data("book_title", subject_id=subject_id)
    if not books:
        print(f"   - FAILED: No books found with subject_id={subject_id}.")
        print("   - Please check your `book_title` table.")
        return
    book = books[0]
    book_id = book['id']
    print(f"   - SUCCESS: Found Book '{book['title']}' (ID: {book_id})")

    # 3. Find Chapters
    print("\n3. Searching for associated Chapters...")
    chapters = get_data("chapters", book_id=book_id)
    if not chapters:
        print(f"   - FAILED: No chapters found with book_id={book_id}.")
        print("   - Please check your `chapters` table.")
        return
    chapter_ids = {c['id']: c['name'] for c in chapters}
    print(f"   - SUCCESS: Found {len(chapters)} chapters:")
    for id, name in chapter_ids.items():
        print(f"     - Chapter: '{name}' (ID: {id})")

    # 4. Find Topics
    print("\n4. Searching for associated Topics...")
    all_topics = []
    for chap_id, chap_name in chapter_ids.items():
        topics = get_data("topics", chapter_id=chap_id)
        if topics:
            print(f"   - Found {len(topics)} topics for chapter '{chap_name}'")
            all_topics.extend(topics)
        else:
            print(f"   - WARNING: No topics found for chapter '{chap_name}'")
    
    if not all_topics:
        print("   - FAILED: No topics found for any of the above chapters.")
        return
    topic_ids = [t['id'] for t in all_topics]
    print(f"   - SUCCESS: Found a total of {len(all_topics)} topics across all chapters.")

    # 5. Find Cards
    print("\n5. Searching for associated Cards...")
    all_cards = []
    for top_id in topic_ids:
        cards = get_data("cards", topic_id=top_id)
        if cards:
            all_cards.extend(cards)

    if not all_cards:
        print("   - FAILED: No cards found for any of the above topics.")
        print("\n--- Conclusion ---")
        print("The data check found chapters and topics but NO flashcards associated with them.")
        print("This confirms that the issue is with the data in the database, not the evaluation script.")
        print("Please ensure that the flashcards for Class 8 Arts have been generated and inserted correctly.")
        return

    print(f"   - SUCCESS: Found a total of {len(all_cards)} cards.")
    print("\n--- Data Check Complete ---")

if __name__ == "__main__":
    run_check()

import os
import json
import time
import math
from openai import OpenAI
import pdfplumber
from supabase import create_client, Client
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")
EVALUATIONS_FILE = '../../accuracy_evaluations.json'
PDF_DIRECTORY = '../../books/class11_biology'
CARD_CHUNK_SIZE = 20 # Increased chunk size for faster evaluation

# --- Initialize Clients ---
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    client = OpenAI(
        api_key=os.getenv("XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
    )
    grok_model = 'grok-4'
except Exception as e:
    print(f"Error initializing clients: {e}")
    exit()

def get_all_data(table_name):
    """Fetches all data from a Supabase table, handling pagination."""
    all_data = []
    current_page = 0
    page_size = 1000
    while True:
        try:
            start_index = current_page * page_size
            response = supabase.table(table_name).select("*").range(start_index, start_index + page_size - 1).execute()
            data = response.data
            all_data.extend(data)
            if len(data) < page_size:
                break
            current_page += 1
        except Exception as e:
            print(f"Error fetching data from {table_name} (page {current_page}): {e}")
            return None
    return all_data

def get_pdf_text(pdf_path):
    """Extracts all text from a PDF file."""
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        return None
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return None

def get_accuracy_evaluation(chapter_text, card_chunk, golden_dataset):
    """Evaluates a chunk of cards for accuracy against the full chapter text."""
    print(f"Evaluating a chunk of {len(card_chunk)} cards for accuracy...")
    prompt = f"""
    You are an accuracy evaluator for educational flashcards. Evaluate answers based *only* on the provided NCERT chapter text.

    **Reference NCERT Chapter Text:**
    --- START OF TEXT ---
    {chapter_text}
    --- END OF TEXT ---

    **Scoring Scale (4-point):**
    *   **1 (Incorrect):** Factually wrong, not in text.
    *   **2 (External):** Correct, but not in text.
    *   **3 (Partial):** Combines text with external info.
    *   **4 (Fully NCERT):** Accurate, directly verifiable from text.

    **Golden Standard Examples:**
    {json.dumps(golden_dataset, indent=None, separators=(',', ':'))}

    **Evaluation Task:**
    For each flashcard in the chunk below, provide accuracy (1-4) and confidence (0-100) scores. Base judgment *solely* on the NCERT text.

    **Flashcard Chunk to Evaluate:**
    {json.dumps(card_chunk, indent=None, separators=(',', ':'))}

    **Required Output (Strict JSON):**
    Respond with only a valid JSON list of evaluation objects. No other text or formatting.
    ```json
    [
      {{
        "card_id": "<uuid>",
        "accuracy_score": <integer_1_to_4>,
        "confidence_score": <integer_0_to_100>,
        "rationale": "<brief explanation>"
      }}
    ]
    ```
    Provide a concise rationale (1-2 sentences) for each card's scores, explaining *why* based *only* on the NCERT text.
    """
    try:
        response = client.chat.completions.create(
            model=grok_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.0 # Set to 0 for deterministic, fact-based evaluation
        )
        cleaned_text = response.choices[0].message.content.strip().replace('```', '').replace('json', '')
        
        # Extract and print token usage
        if response.usage:
            print(f"    Token Usage: Prompt Tokens = {response.usage.prompt_tokens}, Completion Tokens = {response.usage.completion_tokens}, Total Tokens = {response.usage.total_tokens}")

        return json.loads(cleaned_text)
    except Exception as e:
        print(f"Error during card chunk evaluation: {e}")
        return None

def main():
    """Main function to run the chapter-based accuracy evaluation."""
    print("Starting flashcard accuracy evaluation...")

    # 1. Load the golden dataset
    print("Loading golden dataset...")
    try:
        with open('../../dataset/golden_dataset.json', 'r', encoding='utf-8') as f:
            golden_dataset = json.load(f)
    except FileNotFoundError:
        print("Error: golden_dataset.json not found. Please create the dataset first.")
        return
    except json.JSONDecodeError:
        print("Error: golden_dataset.json is not a valid JSON file.")
        return

    # 2. Fetch all data from Supabase
    print("Fetching data from Supabase...")
    subjects, books, chapters, topics, cards = (get_all_data(t) for t in ["subjects", "book_title", "chapters", "topics", "cards"])
    if not all([subjects, books, chapters, topics, cards]):
        print("Could not fetch all required data from Supabase. Exiting.")
        return
    print(f"Loaded {len(cards)} cards across {len(chapters)} chapters.")

    # Create a map for topic names
    topic_map = {topic['id']: topic['name'] for topic in topics}

    # 3. Filter for Class 8 Arts
    try:
        selected_subject = next(s for s in subjects if s['class_name'] == '11' and s['subject_name'].lower() == 'biology')
        subject_id = selected_subject['id']
        class_name = selected_subject['class_name']
        subject_name = selected_subject['subject_name']
        book_id = next(b['id'] for b in books if b['subject_id'] == subject_id)
        selected_chapters = sorted([c for c in chapters if c['book_id'] == book_id], key=lambda x: x['order_index'])
        # Ensure PDF files are sorted to match chapter order
        pdf_files = sorted([f for f in os.listdir(PDF_DIRECTORY) if f.lower().endswith('.pdf')])
    except (StopIteration, FileNotFoundError) as e:
        print(f"Setup error for Class 8 Arts: {e}")
        return

    print(f"Found {len(selected_chapters)} chapters for Class {class_name} {subject_name.capitalize()}.")

    # 4. Process each chapter
    final_evaluations = []
    seen_cards_content = set() # To store (question, answer) tuples for duplicate detection

    # 4. Process only the first chapter and its first topic for testing
    if not selected_chapters:
        print("No chapters found for the selected subject. Exiting.")
        return

    chapter = selected_chapters[0] # Get the first chapter
    if 0 >= len(pdf_files):
        print(f"Warning: No matching PDF found for chapter {chapter['name']}. Skipping.")
        return
    
    chapter_name = chapter['name']
    print(f"\n--- Processing Chapter 1 (for testing): '{chapter_name}' ---")

    # a. Get the full, unsanitized PDF text
    pdf_path = os.path.join(PDF_DIRECTORY, pdf_files[0])
    full_chapter_text = get_pdf_text(pdf_path)
    if not full_chapter_text:
        print(f"Could not read PDF text for {chapter_name}. Skipping.")
        return

    # b. Get all cards for this chapter and filter for the first topic
    chapter_topics = [t for t in topics if t.get('chapter_id') == chapter['id']]
    if not chapter_topics:
        print(f"No topics found for chapter {chapter_name}. Skipping.")
        return
    
    first_topic = chapter_topics[0] # Get the first topic
    topic_ids = {first_topic['id']}
    chapter_cards = [c for c in cards if c.get('topic_id') in topic_ids]
    
    if not chapter_cards:
        print(f"No cards found for the first topic of chapter {chapter_name}. Skipping.")
        return
    
    print(f"Found {len(chapter_cards)} cards for the first topic of this chapter.")

    # c. Perform accuracy evaluation in chunks
    num_chunks = math.ceil(len(chapter_cards) / CARD_CHUNK_SIZE)
    print(f"Splitting cards into {num_chunks} chunks of size {CARD_CHUNK_SIZE}.")
    all_card_evals = []
    for j in range(num_chunks):
        start = j * CARD_CHUNK_SIZE
        end = start + CARD_CHUNK_SIZE
        chunk = chapter_cards[start:end]
        
        print(f"-- Evaluating chunk {j + 1}/{num_chunks} --")
        
        # Prepare chunk with only necessary data for the prompt
        prompt_chunk = [{"card_id": c['id'], "question": c['front'], "answer": c['back']}
                        for c in chunk]
        
        chunk_eval = get_accuracy_evaluation(full_chapter_text, prompt_chunk, golden_dataset)
        if chunk_eval:
            all_card_evals.extend(chunk_eval)
        time.sleep(0.1) # Reduced rate limit delay for faster evaluation
    
    # d. Combine all results into the final structure and check for duplicates
    card_info_map = {}
    for card in chapter_cards:
        topic_name = topic_map.get(card.get('topic_id'), 'Uncategorized')
        card_info_map[card['id']] = {
            "question": card['front'],
            "answer": card['back'],
            "topic_name": topic_name
        }

    for eval_item in all_card_evals:
        card_id = eval_item["card_id"]
        card_info = card_info_map.get(card_id, {})
        
        question = card_info.get("question")
        answer = card_info.get("answer")
        
        is_repeated = False
        if (question, answer) in seen_cards_content:
            is_repeated = True
        else:
            seen_cards_content.add((question, answer))

        final_evaluations.append({
            "card_id": card_id,
            "topic_name": card_info.get("topic_name"),
            "question": question,
            "answer": answer,
            "accuracy_score": eval_item.get("accuracy_score"),
            "confidence_score": eval_item.get("confidence_score"),
            "rationale": eval_item.get("rationale"),
            "is_repeated": is_repeated
        })

    print(f"Successfully evaluated {len(chapter_cards)} cards for the first topic of chapter '{chapter_name}'.")

    # 5. Save the final results
    if final_evaluations:
        with open(EVALUATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_evaluations, f, indent=4, ensure_ascii=False)
        print(f"\nAccuracy evaluation process completed. Results saved to {EVALUATIONS_FILE}")

if __name__ == "__main__":
    main()

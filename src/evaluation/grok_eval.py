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
EVALUATIONS_FILE = '../../chapter_evaluations.json'
PDF_DIRECTORY = '../../books/class8_arts'
CARD_CHUNK_SIZE = 10 # Number of cards to evaluate per API call

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

def get_summary_from_grok(pdf_text, chapter_name):
    """Uses Grok to create a structured summary of the chapter text."""
    print("Requesting chapter summary from Grok...")
    prompt = f"""Please create a concise, structured summary of the following book chapter text, focusing on all key concepts, definitions, and facts. Return only the summary text."""
    try:
        response = client.chat.completions.create(
            model=grok_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error during Grok summary for chapter '{chapter_name}': {e}")
        return None

def get_chapter_exhaustiveness_evaluation(chapter_name, summary, all_card_questions):
    """Evaluates the exhaustiveness of all cards for a chapter."""
    print("Evaluating chapter exhaustiveness...")
    prompt = f"""
    **Task:** Evaluate if the entire set of flashcard questions for the chapter comprehensively covers all topics in the provided summary.
    **Chapter Summary:**
    {summary}
    **All Flashcard Questions:**
    {json.dumps(all_card_questions, indent=2)}

    **Golden Examples:**
    *   **Low Rating (1/5):** A card set for a chapter on 'Elements of Art' only contains cards about the element 'Line'. It completely ignores other crucial elements like Color, Shape, Form, Texture, and Space. **Rationale:** 'The card set is not exhaustive. It focuses on a single sub-topic while ignoring the majority of the chapter's core concepts.'
    *   **Moderate Rating (3/5):** A card set for a chapter on 'Indian Folk Art' covers Madhubani and Warli painting but omits Kalamkari and Gond art, which are also detailed in the chapter. **Rationale:** 'The set is partially exhaustive, covering some major topics but missing others, providing an incomplete overview.'
    *   **High Rating (5/5):** A card set for a chapter on 'Elements of Art' has dedicated cards for Line, Shape, Form, Color (including primary/secondary), Texture, and Space, matching the chapter structure. **Rationale:** 'The card set is fully exhaustive, covering all major and minor concepts presented in the reference text.'

    **IMPORTANT: The score MUST be an integer between 1 (very bad) and 5 (very good).**

    **Required Output (Strict JSON):**
    ```json
    {{ "score": <integer>, "notes": "<string>" }}
    ```
    """
    try:
        response = client.chat.completions.create(
            model=grok_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        )
        cleaned_text = response.choices[0].message.content.strip().replace('```', '').replace('json', '')
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"Error during exhaustiveness evaluation: {e}")
        return None

def get_topic_card_count_evaluation(topic_name, summary, topic_card_questions):
    """Evaluates if the number of cards for a specific topic is optimal."""
    print("Evaluating card count for topic: '{topic_name}'...")
    prompt = f"""
    **Task:** Based on the chapter summary, evaluate if the number of flashcards for the topic '{topic_name}' is optimal (not too many, not too few).
    **Chapter Summary:**
    {summary}
    **Topic Flashcard Questions:**
    {json.dumps(topic_card_questions, indent=2)}

    **Golden Examples:**
    *   **Low Rating (1/5):** A topic on 'Color Theory' has only one card: "What are the primary colors?" **Rationale:** 'Too few. This complex topic requires more cards to cover secondary colors, complementary colors, and color temperature to be useful.'
    *   **Moderate Rating (3/5):** A topic on 'Warli Painting' has 10 cards, but 7 of them are minor variations of "What shape is used in Warli art?" **Rationale:** 'Suboptimal. The card count is inflated with repetitive questions, while other aspects like themes and materials are neglected.'
    *   **High Rating (5/5):** A topic on 'Madhubani Painting' has 5 cards, covering its origin, key characteristics (e.g., geometric patterns), common themes (nature, mythology), and materials used. **Rationale:** 'Optimal. The number of cards is sufficient to cover the topic comprehensively without being redundant.'

    **IMPORTANT: The score MUST be an integer between 1 (very bad) and 5 (very good).**

    **Required Output (Strict JSON):**
    ```json
    {{ "score": <integer>, "notes": "<string>" }}
    ```
    """
    try:
        response = client.chat.completions.create(
            model=grok_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        )
        cleaned_text = response.choices[0].message.content.strip().replace('```', '').replace('json', '')
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"Error during topic card count evaluation for '{topic_name}': {e}")
        return None

def get_card_chunk_evaluation(summary, card_chunk):
    """Evaluates a small chunk of cards for correctness and relevance."""
    print("Evaluating card chunk {j + 1}/{num_chunks}...")
    prompt = f"""
    **Task:** For each card in the chunk, evaluate its correctness and relevance based on the chapter summary.
    **Chapter Summary:**
    {summary}
    **Flashcard Chunk:**
    {json.dumps(card_chunk, indent=2)}

    **Golden Examples:**
    *   **Correctness (1/5):** Q: 'What are the primary colors?' A: 'Blue, Green, and Yellow.' **Rationale:** 'Factually incorrect. Green is a secondary color, not primary.'
    *   **Correctness (3/5):** Q: 'What is a landscape?' A: 'A painting of the outdoors.' **Rationale:** 'Correct but imprecise. It lacks detail, such as mentioning that landscapes typically feature natural scenery like mountains, rivers, or forests.'
    *   **Correctness (5/5):** Q: 'What is texture in art?' A: 'Texture is the element of art that refers to the way things feel, or look as if they might feel if touched.' **Rationale:** 'Perfectly correct, clear, and well-defined.'
    *   **Relevance/Completeness (1/5):** Q: 'What is Madhubani art?' A: 'It is a famous art style.' **Rationale:** 'The answer is completely irrelevant and incomplete. It provides no specific information about Madhubani art.'
    *   **Relevance/Completeness (3/5):** Q: 'What are the key features of Warli painting?' A: 'They use geometric shapes like circles, triangles, and squares.' **Rationale:** 'Relevant but incomplete. It answers part of the question but omits other key features like the use of a white pigment on an earthen background and themes of daily life.'
    *   **Relevance/Completeness (5/5):** Q: 'What are the key features of Warli painting?' A: 'Warli paintings are characterized by their use of basic geometric shapes (circles, triangles, squares), a monochrome palette (white pigment on a red or brown background), and themes depicting scenes from daily life, nature, and rituals.' **Rationale:** 'Perfectly relevant and complete, addressing all aspects of the question.'

    **IMPORTANT: All scores MUST be an integer between 1 (very bad) and 5 (very good).**

    **Required Output (Strict JSON):** A list of evaluation objects.
    ```json
    [
      {{
        "card_id": "<uuid>",
        "correctness": {{ "score": <integer>, "notes": "<string>" }},
        "relevance": {{ "score": <integer>, "notes": "<string>" }}
      }}
    ]
    ```
    """
    try:
        response = client.chat.completions.create(
            model=grok_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ]
        )
        cleaned_text = response.choices[0].message.content.strip().replace('```', '').replace('json', '')
        return json.loads(cleaned_text)
    except Exception as e:
        print(f"Error during card chunk evaluation: {e}")
        return None

def main():
    """Main function to run the chapter-based evaluation."""
    print("Starting chapter-based flashcard evaluation...")

    # 1. Fetch all data
    print("Fetching data from Supabase...")
    subjects, books, chapters, topics, cards = (get_all_data(t) for t in ["subjects", "book_title", "chapters", "topics", "cards"])
    if not all([subjects, books, chapters, topics, cards]): return
    print(f"Loaded {len(cards)} cards across {len(chapters)} chapters.")

    # 2. Filter for Class 8 Arts
    try:
        subject_id = next(s['id'] for s in subjects if s['class_name'] == '8' and s['subject_name'].lower() == 'arts')
        book_id = next(b['id'] for b in books if b['subject_id'] == subject_id)
        selected_chapters = sorted([c for c in chapters if c['book_id'] == book_id], key=lambda x: x['order_index'])
        pdf_files = sorted([f for f in os.listdir(PDF_DIRECTORY) if f.lower().endswith('.pdf')])
    except (StopIteration, FileNotFoundError) as e:
        print(f"Setup error: {e}")
        return

    # 3. Process each chapter
    final_evaluations = []
    for i, chapter in enumerate(selected_chapters):
        if i >= len(pdf_files): break
        chapter_name = chapter['name']
        print(f"\n--- Processing Chapter {i + 1}/{len(selected_chapters)}: '{chapter_name}' ---")

        # a. Get PDF text and summary
        pdf_path = os.path.join(PDF_DIRECTORY, pdf_files[i])
        pdf_text = get_pdf_text(pdf_path)
        if not pdf_text: continue
        summary = get_summary_from_grok(pdf_text, chapter_name)
        if not summary: continue
        time.sleep(1)

        # b. Get cards and topics for this chapter
        chapter_topics = [t for t in topics if t.get('chapter_id') == chapter['id']]
        topic_map = {t['id']: t['name'] for t in chapter_topics}
        chapter_cards = [c for c in cards if c.get('topic_id') in topic_map]
        if not chapter_cards: continue

        # c. Perform chapter-level exhaustiveness evaluation
        all_card_questions = [{"id": c['id'], "question": c['front']} for c in chapter_cards]
        exhaustiveness_eval = get_chapter_exhaustiveness_evaluation(chapter_name, summary, all_card_questions)
        time.sleep(1)

        # d. Perform topic-level card count evaluation
        topic_evaluations = []
        for topic_id, topic_name in topic_map.items():
            topic_cards = [c for c in chapter_cards if c.get('topic_id') == topic_id]
            if not topic_cards: continue
            print(f"Evaluating card count for topic: '{topic_name}'...")
            topic_card_questions = [{"id": c['id'], "question": c['front']} for c in topic_cards]
            count_eval = get_topic_card_count_evaluation(topic_name, summary, topic_card_questions)
            topic_evaluations.append({"topic_name": topic_name, "evaluation": count_eval})
            time.sleep(1)

        # e. Perform card-level evaluation in chunks
        num_chunks = math.ceil(len(chapter_cards) / CARD_CHUNK_SIZE)
        all_card_evals = []
        for j in range(num_chunks):
            start = j * CARD_CHUNK_SIZE
            end = start + CARD_CHUNK_SIZE
            chunk = chapter_cards[start:end]
            print(f"Evaluating card chunk {j + 1}/{num_chunks}...")
            chunk_eval = get_card_chunk_evaluation(summary, chunk)
            if chunk_eval: all_card_evals.extend(chunk_eval)
            time.sleep(2)
        
        # f. Combine all results into final structure
        card_content_map = {c['id']: {"front": c['front'], "back": c['back']} for c in chapter_cards}
        final_card_results = []
        for eval_item in all_card_evals:
            card_id = eval_item["card_id"]
            final_card_results.append({
                "card_id": card_id,
                "content": card_content_map.get(card_id, {}),
                "correctness": eval_item.get("correctness"),
                "relevance": eval_item.get("relevance")
            })

        final_evaluations.append({
            "chapter_name": chapter_name,
            "exhaustiveness": exhaustiveness_eval,
            "optimal_card_count_per_topic": topic_evaluations,
            "card_evaluations": final_card_results
        })
        print(f"Successfully evaluated chapter '{chapter_name}'.")

    # 4. Save results
    if final_evaluations:
        with open(EVALUATIONS_FILE, 'w') as f:
            json.dump(final_evaluations, f, indent=4)
        print(f"\nEvaluation process completed. Results saved to {EVALUATIONS_FILE}")

if __name__ == "__main__":
    main()
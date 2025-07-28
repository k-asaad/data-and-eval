import os
import pdfplumber
from dotenv import load_dotenv
from google import genai

# Load environment variables from .env
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
client = genai.Client()
preferred_model = "gemini-1.5-pro-latest"
# preferred_model = "gemini-2.0-flash"

def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

def extract_chapter_name_from_text(chapter_text):
    # Assumes the chapter name is the first non-empty line
    for line in chapter_text.splitlines():
        if line.strip():
            return line.strip()
    return "Unknown Chapter"

def generate_sql_from_text(
    chapter_text, class_name, subject_name, book_title, book_icon, book_color, language, chapter_name, flashcards_per_topic
):
        # --- LLM PROMPT CONSTRUCTION ---
    sample_sql = '''
DO $$
DECLARE
  _subject_id uuid;
  _book_id uuid;
  _chapter_id uuid;
  _topic_id uuid;
  _order_index int;
BEGIN

  -- Subject
  SELECT id INTO _subject_id FROM subjects WHERE class_name = '7' AND subject_name = 'English';
  IF _subject_id IS NULL THEN
    INSERT INTO subjects (id, class_name, subject_name, icon, color, description, created_at)
    VALUES (gen_random_uuid(), '7', 'English', 'english_icon', 'green', 'English Subject for Class 7', NOW())
    RETURNING id INTO _subject_id;
    RAISE NOTICE 'Subject inserted: %', _subject_id;
  ELSE
    RAISE NOTICE 'Subject found: %', _subject_id;
  END IF;

  -- Book Title
  SELECT id INTO _book_id FROM book_title WHERE subject_id = _subject_id AND title = 'Poorvi';
  IF _book_id IS NULL THEN
    INSERT INTO book_title (id, subject_id, title)
    VALUES (gen_random_uuid(), _subject_id, 'Poorvi')
    RETURNING id INTO _book_id;
    RAISE NOTICE 'Book Title inserted: %', _book_id;
  ELSE
    RAISE NOTICE 'Book Title found: %', _book_id;
  END IF;

    -- Chapter
    SELECT id INTO _chapter_id FROM chapters WHERE book_id = _book_id AND name = 'Bravehearts';
    IF _chapter_id IS NULL THEN
      INSERT INTO chapters (id, book_id, name, order_index)
      VALUES (gen_random_uuid(), _book_id, 'Bravehearts', 1) -- Assuming order_index 1
      RETURNING id INTO _chapter_id;
      RAISE NOTICE 'Chapter inserted: %', _chapter_id;
    ELSE
      RAISE NOTICE 'Chapter found: %', _chapter_id;
    END IF;

-- Topics and Cards
_order_index := 1;

-- Topic 1: A Homage to Our Brave Soldiers
SELECT id INTO _topic_id FROM topics WHERE chapter_id = _chapter_id and name = 'A Homage to Our Brave Soldiers';
IF _topic_id IS NULL THEN
INSERT INTO topics (id, chapter_id, name, order_index)
VALUES (gen_random_uuid(), _chapter_id, 'A Homage to Our Brave Soldiers', _order_index)
RETURNING id INTO _topic_id;
_order_index := _order_index + 1;
END IF;

INSERT INTO cards (id, topic_id, front, back, card_type, order_index)
SELECT gen_random_uuid(), _topic_id, front, back, card_type, order_index from (
VALUES
  ('What does ''homage'' mean?', 'Something done to show respect publicly.', 'basic', 1),
  -- ... more cards ...
) as cards_data(front, back, card_type, order_index);

RAISE NOTICE 'Cards inserted successfully.';

EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'An error occurred: %', SQLERRM;
END $$;
'''

    prompt = f"""
You are an expert NCERT SQL flashcard generator. Generate a full **PostgreSQL PL/pgSQL script** for the chapter **\"{chapter_name}\"** from Class {class_name}, Subject **\"{subject_name.capitalize()}\"**, Book Title: **\"{book_title}\"**.

- In this subject go through the pdf and fetch or generate meaningful topics name from the chapter give them a name don't just write 1.1, 1.2 etc text also the length of the topic must not be too big max 2 - 3 words.
- Don't make problem solving cards it is mathematics so make cards that are meaningful and helpful to learn concepts of mathematics like that no any problem solving type.
- This book contains topics and do you know sections so make sure all these are included in the flashcards but also make sure the questions and answers of that cards are meaningful because currently the cards are read only
- Create 5-6 topics from the chapter text and generate cards for each topic which are meaningful and relevant to the chapter.
- Also make sure the Chapter order is correct 1, 2, 3, etc.
-  Not only topic like 1.1 , 1.2 also some heading include that also 
- Generate the complete SQL block in one single output.
- Produce all topics in full, with all meaningful and non-repetitive flashcards related to each topic. No truncation, no splitting into multiple parts, no summarizing, no "add the rest" instructions, no placeholders.
- Output a single, complete, valid SQL block with proper escaping of single quotes. No markdown formatting. No explanations. Just the final SQL.
- Also: Do not stop in between. Make sure the entire chapter’s topics and cards are present in the single response, even if long.
- The format must exactly match the INSERT statements shown earlier. Each topic’s block must include all its cards and any sub-topic cards merged.
-- Ensure each topic has cards. All topics and subsections from the chapter text must be present.
- Also make sure the Chapter order is correct 1, 2, 3, etc.
- Also fetch the full name of the chapter.

---

🔚 Final Output Requirement:
**Only return a full, working SQL block**. Do not output anything else. No Markdown, no comments, no "here's your SQL", just raw executable SQL text.

---
## 🛠️ TASK:
Generate a complete SQL script that:
1. Checks if the subject, book title, chapter, and topics exist before inserting. If not, insert and fetch their UUIDs using SELECT INTO, IF ... IS NULL THEN INSERT ... RETURNING INTO, etc.
3. For each topic, generates {flashcards_per_topic} meaningful flashcards (mix of types) with all single quotes escaped as two single quotes.
4. Uses only these tables and columns:
   - subjects: id, class_name, subject_name, icon, color, description, created_at
   - book_title: id, subject_id, title
   - chapters: id, book_id, name, order_index
   - topics: id, chapter_id, name, order_index
   - cards: id, topic_id, front, back, card_type, order_index
5. The script must be production-quality, error-free, and ready for Supabase SQL Editor. Do not use plain INSERTs without existence checks. Do not use markdown, comments, or explanations in the output. Do not stop mid-script.

---
## 📚 INPUT STRUCTURE
- Class: {class_name}
- Subject: {subject_name.capitalize()} -- NOTE : here in the subject please write like this Physical Education and Wellbeing
- Book Title: {book_title}
- Book Icon: {book_icon}
- Book Color: {book_color}
- Language: {language} 
- Chapter Name: {chapter_name}
- Chapter Text: (see below)

## SAMPLE SQL STRUCTURE (STRICTLY FOLLOW THIS)
{sample_sql}

---
## ✅ REQUIREMENTS
1. Extract the **actual chapter name** from the provided chapter text (not the filename).
    - also don't mention thing like Chapter1 : , or Unit 1: , only the chapter name in the sql.
2. Extract unique, relevant topics from the chapter text (use headings or infer if needed).
   -For this case the chapter have topic inside the pdf labelled as 1.1, 1.2, 1.3 or 2.1, 2.2 etc like this so the topic will be same as the number of marking like this in each chapter.
3. For each topic:
   - Generate **{flashcards_per_topic} meaningful flashcards** in {language}.
   - Mix types: `basic`, `fill_in_the_blank`.
   - Each card must have a non-empty question and answer.
   - No references to images, figures, or page numbers.
   - All single quotes in string values must be escaped as two single quotes.
4. SQL must include:
   - Existence checks and conditional inserts for all entities (subject, book title, chapter, topics)
   - Variable assignment for UUIDs
   - DO $$ DECLARE ... BEGIN ... END $$; blocks
   - RAISE NOTICE for success/failure
   - EXCEPTION WHEN OTHERS for error handling
   - All values must use gen_random_uuid() for id
5. The entire script must be **complete, clean, and executable** in the Supabase SQL Editor.

---
## ⚠️ SQL STRING ESCAPING RULES (MANDATORY)
- Escape **all single quotes `'`** in string values using **two single quotes `''`**.
  - Example: `'Anand''s latest invention'`
- Do this for both `front` and `back` fields.
- Do **not** use backslashes or `\"` — only use `''`.

---
## ✅ SQL FORMAT RULES
- Use DO $$ DECLARE ... BEGIN ... END $$; blocks
- Use SELECT INTO, IF ... IS NULL THEN INSERT ... RETURNING INTO, etc.
- Use gen_random_uuid() for all new rows
- Only valid SQL compatible with Supabase
- Do NOT use plain INSERTs without existence checks
- Do NOT use markdown, comments, or explanations in the output

---
## ⚠️ FINAL ENFORCEMENT
- Do not skip any topic
- Do not include placeholders like:
  - `-- Add next topic here`
  - `-- Example cards`
- Only valid SQL
- Every topic must have {flashcards_per_topic} **complete** flashcards
- The script must run without errors in Supabase SQL Editor. If you use a table or column name that does not exist, the SQL will fail. Use only these columns:
  - subjects: id, class_name, subject_name, icon, color, description, created_at
  - book_title: id, subject_id, title
  - chapters: id, book_id, name, order_index
  - topics: id, chapter_id, name, order_index
  - cards: id, topic_id, front, back, card_type, order_index

---
# Chapter Text:
{chapter_text}

---
Return only the final, full SQL. Do not stop mid-script. Do not skip any topic. Do not use markdown.
"""
    response = client.models.generate_content(
        model=preferred_model,
        contents=prompt
    )
    return response.text

def main():
    class_name = input("Enter class (e.g., 7): ").strip()
    subject_name = input("Enter subject (e.g., english): ").strip().lower()
    book_title = input("Enter book title (e.g., Poorvi): ").strip()
    # book_icon and book_color are now set by default
    book_icon = 'english_icon'
    book_color = 'green'
    language = input("Enter language for flashcards (e.g., English): ").strip()
    flashcards_per_topic = input("Enter number of flashcards per topic (e.g., 20): ").strip()
    try:
        flashcards_per_topic = int(flashcards_per_topic)
    except ValueError:
        print("Invalid number. Using default of 20 flashcards per topic.")
        flashcards_per_topic = 20
    
    folder = os.path.join("../../books", f"class{class_name}_{subject_name}")
    output_dir = "../../output"
    os.makedirs(output_dir, exist_ok=True)
    if not os.path.isdir(folder):
        print(f"Folder {folder} does not exist. Please check your input.")
        return
    for filename in os.listdir(folder):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(folder, filename)
            chapter_text = extract_text_from_pdf(pdf_path)
            chapter_name = extract_chapter_name_from_text(chapter_text)
            sql = generate_sql_from_text(
                chapter_text, class_name, subject_name, book_title, book_icon, book_color, language, chapter_name, flashcards_per_topic
            )
            with open(os.path.join(output_dir, f"{filename.replace('.pdf', '')}.sql"), "w", encoding="utf-8") as f:
                f.write(sql)
            print(f"Generated SQL for {chapter_name}")

if __name__ == "__main__":
    main() 
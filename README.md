# NCERT Flashcard Generation and Evaluation

This project is a data pipeline for generating educational flashcards from NCERT textbooks and evaluating their quality using large language models.

## Features

*   **Automated Flashcard Generation:** Extracts text from PDF textbooks and uses a large language model to generate flashcards in the form of a PostgreSQL script.
*   **AI-Powered Evaluation:** Uses large language models (Gemini or Grok) to evaluate the generated flashcards based on exhaustiveness, optimal card count, correctness, and relevance.
*   **Supabase Integration:** The generated SQL scripts are designed to be run in a Supabase environment to populate a database with the flashcard content.
*   **Structured Codebase:** The project is organized into separate directories for SQL generation, AI evaluation, and utility scripts.

## Project Structure

```
. 
├── books/ # Directory for PDF textbooks 
├── output/ # Directory for generated SQL files 
├── scripts/ # Utility scripts 
│ ├── data_check.py # Script to diagnose data integrity issues 
│ └── supabase-run.py # Script to execute generated SQL files 
├── src/ # Source code 
│ ├── evaluation/ # AI evaluation scripts 
│ │ ├── grok_eval.py # Evaluation script using Grok 
│ │ └── run_evaluation.py # Evaluation script using Gemini 
│ └── generation/ # SQL generation scripts 
│ ├── main.py # Main script for generating SQL files 
│ └── prompt.txt # Prompt for the large language model 
├── .env # Environment variables (not committed) 
├── .gitignore # Git ignore file 
├── README.md # Project documentation 
└── requirements.txt # Python dependencies
```

## Setup and Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/<your-username>/data-and-eval.git
    cd data-and-eval
    ```

2.  **Create and activate a virtual environment:**

    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install the required dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your environment variables:**

    Create a file named `.env` in the root of the project and add the following environment variables:

    ```
    SUPABASE_URL="your_supabase_url"
    SUPABASE_KEY="your_supabase_key"
    GEMINI_API_KEY="your_gemini_api_key"
    XAI_API_KEY="your_xai_api_key"
    ```

## Running the Application

### Backend

To run the backend services, you will need to have Python and pip installed. You will also need to have a Supabase account and a Grok account.

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/<your-username>/data-and-eval.git
    cd data-and-eval
    ```

2.  **Create and activate a virtual environment:**

    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install the required dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your environment variables:**

    Create a file named `.env` in the root of the project and add the following environment variables:

    ```
    SUPABASE_URL="your_supabase_url"
    SUPABASE_KEY="your_supabase_key"
    GEMINI_API_KEY="your_gemini_api_key"
    XAI_API_KEY="your_xai_api_key"
    ```

5.  **Generate SQL files:**

    ```bash
    python src/generation/main.py
    ```

6.  **Run the evaluation:**

    ```bash
    python src/evaluation/evaluate_accuracy.py
    ```

7.  **Run the Supabase script:**

    ```bash
    python scripts/supabase-run.py
    ```

### Viewing the Evaluation Report

After running the accuracy evaluation, you can view the results by opening the `evaluation_report.html` file in your web browser. This file will automatically load and display the data from `accuracy_evaluations.json`.

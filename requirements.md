# Project: Autonomous Assistant for Math Tutors
**Focus:** Multimodal AI Agent for Handwriting Analysis & Lesson Management
**Infrastructure:** AWS Bedrock (Claude 3.5 Sonnet), LangChain, Google Workspace API.

---

## 1. Project Goal
An intelligent agent that automates the workflow of a professional math tutor. The agent analyzes handwritten notes (Goodnotes/PDF), tracks student progress across mathematical topics, and manages lessons via Google Calendar.

## 2. Technical Stack
* **Orchestration:** LangChain (Agentic Workflow).
* **LLM (Vision & Reasoning):** Amazon Bedrock - `anthropic.claude-3-5-sonnet-20240620-v1:0`.
* **Frontend:** Streamlit (Tutor Dashboard).
* **APIs:** 
    * Google Drive API (Handwritten notes storage).
    * Google Calendar API (Lesson scheduling).
    * Twilio/SendGrid (Optional: notifications for students).
* **Environment:** Cursor.ai, Python 3.10+, `pdf2image` for PDF processing.

---

## 3. Core Functional Requirements (Math Focus)

### FR1: Handwriting & Formula Analysis (Vision Tool)
* **Input:** PDF files exported from Goodnotes/Tablets.
* **Process:** 
    1. Fetch the latest PDF from the student's folder on Google Drive.
    2. Convert PDF pages to high-res images.
    3. Use Claude 3.5 Sonnet to perform OCR on handwritten formulas and text.
* **Logic:** Identify solved problems, detected errors, and topics covered (e.g., "Quadratic Equations", "Integrals").

### FR2: Progress Tracking & Gap Analysis
* **Action:** Compare current lesson content with the national curriculum (e.g., Matura exam requirements).
* **Output:** A "Student Progress Map" showing which topics are mastered and which need more practice.

### FR3: Daily Briefing for Tutor
* **Action:** Daily automated report triggered by Google Calendar.
* **Content:** 
    * "Today you have 3 students."
    * "Student A: Last time we did Trigonometry. They struggled with Sine Rule in their homework. Suggested today: 5 practice problems on Sine/Cosine Rules."

### FR4: Onboarding & Workspace Provisioning
* **Action:** Creating a standardized environment for a new student.
* **Logic:** 
    1. Create a Google Drive folder: `Students/[Student_Name]/Notes` and `Students/[Student_Name]/Homework`.
    2. Create a recurring event in Google Calendar.
    3. Generate a "Starter Pack" PDF with the tutor's rules and links to the folders.

### FR5: Vacation & Rescheduling Agent
* **Action:** Handle "Tutor is sick/away" scenarios.
* **Logic:** Move Google Calendar events and draft a professional SMS/Email to students with an alternative booking link.

---

## 4. Agent Architecture

### Tools Definitions:
1. `fetch_latest_notes(student_id)`: Downloads and prepares images from the latest PDF on Drive.
2. `analyze_math_content(images)`: Sends images to Bedrock with a prompt to extract math topics and errors.
3. `get_daily_schedule()`: Reads Google Calendar for the current day.
4. `update_student_progress_file()`: Logs identified gaps into a `progress.json` stored on Drive.

### System Prompt Guidelines:
* You are an **Expert Math Assistant**.
* You understand LaTeX and can interpret handwritten mathematical notation.
* You are proactive – if a student makes the same mistake twice in their notes, highlight it as a "Critical Gap".

---

## 5. Deployment & DevOps (AWS)
* **Hosting:** AWS App Runner (Streamlit container).
* **Security:** AWS IAM for Bedrock access.
* **Secrets Management:** Environment variables (no keys in repo).
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

### FR6: Matura Exam Grading (Automated PDF Assessment)
* **Input:** A completed matura exam answer sheet submitted by the teacher as a PDF file
  (e.g., exported from a tablet or scanned).
* **Process:**
  1. Teacher uploads the filled-in PDF via the Streamlit dashboard.
  2. `pdf2image` converts each PDF page to a high-resolution image.
  3. Claude 3.5 Sonnet (Vision) performs OCR on the handwritten/printed responses,
     extracting candidate answers for each sub-task.
  4. The agent fetches the official **marking scheme** from the knowledge base (e.g., S3
     bucket key `marking_schemes/{exam_id}.json`) using the new `fetch_marking_scheme` tool.
  5. Each extracted answer is compared against the marking scheme: full marks, partial
     marks, or zero are awarded per sub-task, following the official CKE (Centralna
     Komisja Egzaminacyjna) criteria.
  6. A structured **grading report** is generated, showing: earned vs. maximum points per
     task, total score, percentage, and a per-task justification for awarded/deducted marks.
* **Output:**
  * A PDF grading report downloadable from the dashboard.
  * Optional: log the result to the student's `progress.json` on Google Drive
    (links matura performance with the ongoing progress tracking in FR2).
* **Knowledge Base Integration:**
  * Marking schemes are stored in an S3 bucket (e.g., `s3://tutor-agent-assets/marking_schemes/`).
  * Exam schemas are keyed by exam type and year (e.g., `matura_math_2024_podstawa.json`).
  * Each schema contains: task IDs, accepted answer variants, point allocations, and
    tolerance rules for numeric answers.

---

## 4. Agent Architecture

### Tools Definitions:
1. `fetch_latest_notes(student_id)`: Downloads and prepares images from the latest PDF on Drive.
2. `analyze_math_content(images)`: Sends images to Bedrock with a prompt to extract math topics and errors.
3. `get_daily_schedule()`: Reads Google Calendar for the current day.
4. `update_student_progress_file()`: Logs identified gaps into a `progress.json` stored on Drive.
5. `fetch_marking_scheme(exam_id)`: Retrieves the official matura marking scheme JSON
   from S3 for the given exam identifier. Used exclusively by the FR6 grading workflow.
6. `grade_matura_submission(images, marking_scheme)`: Sends exam page images alongside
   the marking scheme to Bedrock; returns a structured JSON of per-task scores and
   justifications.

### System Prompt Guidelines:
* You are an **Expert Math Assistant**.
* You understand LaTeX and can interpret handwritten mathematical notation.
* You are proactive – if a student makes the same mistake twice in their notes, highlight it as a "Critical Gap".

---

## 5. Deployment & DevOps (AWS)
* **Hosting:** AWS App Runner (Streamlit container).
* **Security:** AWS IAM for Bedrock access.
* **Secrets Management:** Environment variables (no keys in repo).
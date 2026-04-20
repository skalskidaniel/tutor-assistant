# Teacher Assistant AI Agent

The target users are Polish teachers, and all conversations must be in Polish.

## Use Cases

1. Daily summary before work.
2. Welcoming a new student.
3. Vacation notifications.
4. Google Drive cleanup.
5. Homework management.

### Use Case 1: Daily summary before work

1. The teacher receives a comprehensive summary of how many classes they have that day and with whom, based on Google Calendar.
2. For each lesson, the teacher gets a reminder of what was done last time with this student, based on the most recently modified Google Drive PDF, along with statistics on how many exercises of each type were completed last time.
3. Each new section learned during lessons has its own PDF. For example, if a student is working on quadratic functions for a whole month across multiple lessons, all content about that topic is stored in one PDF. Each PDF is responsible for one section, such as "wielomiany", "stereometria", or "geometria".

### Use Case 2: Welcoming a new student

1. The teacher has made contact with a new student.
2. The agent must create a personalized Google Meet link for the student.
3. The agent must create a personalized Google Drive directory for the student and allow them to see its contents via a shared URL.
4. The agent must create a directory with a structure like the one below:

```text
imie-nazwisko/
├── zadania-domowe/
│   ├── funkcja-kwadratowa.pdf
│   └── wielomiany.pdf
└── notatki/
    ├── funkcja-kwadratowa.pdf
    ├── planimetria.pdf
    ├── geometria-analityczna.pdf
    └── wzory-viete.pdf
```

5. The agent creates a message that the teacher can copy and paste to send to the student.

### Use Case 3: Vacation notifications

1. The teacher informs the agent about their unavailability.
2. The agent prepares a personalized message for each student affected by the teacher's leave.
3. The message contains: "Cześć, musimy przełożyć/odwołać nasze zajęcia z dnia/dni <data> z powodu mojej nieobecności. Możesz sprawdzić dostępne terminy w moim harmonogramie: https://calendar.app.google/wYDwAzjcXXfHD9bx5".

### Use Case 4: Google Drive cleanup

1. The agent browses all students' folders and selects which documents from the "zadania domowe" directory can be removed, based on the publication date. Files older than two months should be removed.
2. The agent renames all files inside the "notatki" folder using the convention of lowercase words separated by hyphens.

### Use Case 5: Homework management

1. The teacher may ask the agent to upload homework to the students' folders for the classes they just had.
2. The homework documents are selected from the teacher's "homework database", which contains files named according to the content inside.

## Agent Chat (LangGraph + Bedrock)

Interactive chat mode is available through CLI:

```bash
uv run python -m tutor_assistant chat
```

Type `exit` or `quit` to close the session.

Useful optional arguments:

- `--calendar-id`
- `--drive-parent-folder-id`
- `--homework-db-folder-id`
- `--thread-id`

### Bedrock model configuration via `.env`

- `BEDROCK_AGENT_MODEL_ID` - model used by conversational agent (LangGraph chat)
- `BEDROCK_TASK_MODEL_ID` - model used by task analyzers (daily summary, homework matcher)

Both values can point to different Bedrock model IDs, so you can test model combinations independently.

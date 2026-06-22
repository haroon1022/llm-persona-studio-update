# LLM Persona Studio

A Streamlit prototype for an MSc project on **LLM-based personas for inclusive design**.

The system follows this core flow:

```text
Project context → Generate multiple personas → Attach design files if needed → Chat with personas → Microsoft Forms feedback
```

The main purpose of the interface is to help a designer, software engineer or researcher create and interrogate multiple personas for a given design project. The feedback link is included only for evaluating the prototype.

## Main features

- Project setup page for entering a design context.
- Project list in the left sidebar for switching between multiple projects.
- Automatic generation of three project-relevant personas.
- Editable persona cards so users can adapt personas to their own case.
- Option to add an additional custom persona manually.
- Attachment support for design images and documents: PNG, JPG, PDF, DOCX, TXT and MD.
- Chat interface for asking personas about the project and attached design material.
- Top-level Feedback button that links directly to the Microsoft Forms questionnaire.
- Lightweight reminder after users have interacted with personas.
- SQLite storage for projects, personas, chat logs and attachment metadata.
- Demo mode if no LLM API key is configured.

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Optional environment variables

Create a `.env` file locally or add these as Streamlit Cloud secrets:

```toml
OPENAI_API_KEY="sk-..."
OPENAI_MODEL="gpt-4o-mini"
```

If no `OPENAI_API_KEY` is provided, the app uses a transparent demo response generator so the interface still works. Image/document-aware responses require an API key and a vision-capable model.

## Evaluation logic

RQ1 is supported by:

- generated personas,
- chat logs,
- a persona-consistency rubric,
- participant ratings on response consistency, relevance, realism and avoidance of stereotypes.

RQ2 is supported mainly by:

- participant feedback about usefulness,
- usability,
- support for inclusive design,
- open comments collected through the linked Microsoft Forms questionnaire.

## Ethical note

Generated personas are simulated viewpoints. They are intended for early-stage reflection and hypothesis generation, not as evidence that replaces real users or participatory design.

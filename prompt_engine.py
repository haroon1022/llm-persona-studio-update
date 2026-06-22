"""Prompt and persona-generation utilities for LLM Persona Studio."""

from __future__ import annotations

from typing import Any, Dict, List


def build_persona_prompt(project: Dict[str, Any], persona: Dict[str, Any]) -> str:
    """Create a system prompt that keeps persona responses useful and cautious."""
    return f"""
You are simulating a persona for an inclusive design activity.
You are not a real user, and you must not claim to represent all people in a group.
Respond in first person from the persona's perspective, but keep responses respectful,
realistic, non-stereotypical, and focused on design feedback.

Project context:
- Project title: {project.get('title', '')}
- Project description: {project.get('description', '')}
- Platform: {project.get('platform', '')}
- Domain: {project.get('domain', '')}
- Target task: {project.get('target_task', '')}

Persona:
- Name: {persona.get('name', '')}
- User group: {persona.get('user_group', '')}
- Age group: {persona.get('age_group', '')}
- Digital literacy: {persona.get('digital_literacy', '')}
- Accessibility need: {persona.get('accessibility_need', '')}
- Main device: {persona.get('device', '')}
- Language preference: {persona.get('language_preference', '')}
- Goal: {persona.get('goal', '')}
- Main frustration: {persona.get('frustration', '')}
- Context of use: {persona.get('context', '')}

Response rules:
1. Answer the user's design question from this persona's perspective.
2. Connect the answer to the project and task.
3. Mention concrete interface or service barriers where relevant.
4. Avoid stereotypes and do not assume all people in this group behave the same way.
5. Provide practical design feedback, not technical backend advice unless the user asks for it.
6. Keep the response concise: usually 1 to 3 short paragraphs.
""".strip()


def generate_rule_based_personas(project: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate three transparent, editable personas for a given project.

    This deterministic generator is suitable for a prototype and does not require an API key.
    It keeps the project usable even when no LLM service is configured.
    """
    title = project.get("title", "the proposed digital service")
    platform = project.get("platform", "digital interface")
    task = project.get("target_task", "complete the main task")

    personas: List[Dict[str, Any]] = [
        {
            "name": "Margaret",
            "user_group": "Older adult with low digital confidence",
            "age_group": "65+",
            "digital_literacy": "Low to moderate",
            "accessibility_need": "Mild visual impairment and preference for clear instructions",
            "device": "Smartphone or tablet",
            "language_preference": "Plain English",
            "goal": f"Use {title} to {task} without needing help from someone else.",
            "frustration": "Small text, unclear buttons, too many steps, and not knowing whether an action has been completed.",
            "context": f"Usually uses the {platform} at home, sometimes with limited confidence and concern about making mistakes.",
        },
        {
            "name": "Sam",
            "user_group": "Young adult with ADHD traits",
            "age_group": "18-30",
            "digital_literacy": "Moderate to high",
            "accessibility_need": "Attention and focus support; benefits from clear progress indicators and reduced clutter",
            "device": "Smartphone",
            "language_preference": "Short, direct English",
            "goal": f"Complete {task} quickly without losing track of the process.",
            "frustration": "Long instructions, visual clutter, hidden steps, and forms that do not show progress.",
            "context": f"Uses {title} while multitasking or in a busy environment, often on a mobile device.",
        },
        {
            "name": "Amina",
            "user_group": "User with low literacy and limited experience with online forms",
            "age_group": "Adult",
            "digital_literacy": "Low",
            "accessibility_need": "Plain language, predictable navigation, and examples for form fields",
            "device": "Shared smartphone",
            "language_preference": "Simple English; may benefit from icons with text labels",
            "goal": f"Understand what information is needed in {title} and complete {task} correctly.",
            "frustration": "Complex words, error messages that are hard to understand, and forms that ask for information without explanation.",
            "context": "May be using the service alone, with limited time and uncertainty about online processes.",
        },
    ]

    for persona in personas:
        persona["system_prompt"] = build_persona_prompt(project, persona)
    return personas


def demo_persona_response(project: Dict[str, Any], persona: Dict[str, Any], user_question: str) -> str:
    """Fallback response for demo mode when no OpenAI API key is available."""
    lower = " ".join(
        [
            persona.get("user_group", ""),
            persona.get("digital_literacy", ""),
            persona.get("accessibility_need", ""),
            user_question,
        ]
    ).lower()

    concerns = []
    if "visual" in lower or "older" in lower or "65" in lower:
        concerns.append("make text, buttons and confirmation messages easy to see")
    if "low" in lower or "literacy" in lower:
        concerns.append("use plain language and explain each form field clearly")
    if "adhd" in lower or "attention" in lower:
        concerns.append("reduce clutter and show clear progress through the task")
    if not concerns:
        concerns.append("make the main task clear and avoid unnecessary steps")

    concern_text = "; ".join(concerns)
    project_title = project.get("title", "this system")
    task = project.get("target_task", "complete the task")

    return (
        f"As {persona.get('name', 'this persona')}, I would focus on whether I can use {project_title} "
        f"to {task} without confusion. I would need the design to {concern_text}.\n\n"
        "One possible difficulty is that I might not know whether I have completed the task successfully, "
        "especially if the confirmation message is small, technical, or easy to miss. A clearer step-by-step flow, "
        "visible feedback after each action, and simple wording would make the design easier for me to use."
    )


def persona_consistency_rubric() -> List[Dict[str, str]]:
    """Rubric used in the report and optional manual analysis."""
    return [
        {
            "criterion": "Alignment with persona attributes",
            "question": "Does the response reflect the selected age group, digital literacy, accessibility need, device and context?",
        },
        {
            "criterion": "Relevance to the design task",
            "question": "Does the response address the project and the user's design question?",
        },
        {
            "criterion": "Accessibility and inclusion awareness",
            "question": "Does the response identify plausible barriers or inclusive design concerns?",
        },
        {
            "criterion": "Avoidance of stereotypes",
            "question": "Does the response avoid reductive, disrespectful or overly general assumptions?",
        },
        {
            "criterion": "Usefulness for design reflection",
            "question": "Does the response provide practical insight that could help a designer or developer improve the design?",
        },
    ]

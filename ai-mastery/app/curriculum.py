import json
import re
import markdown


def parse_curriculum_weeks(md_content: str) -> list[dict]:
    """Parse the markdown curriculum into structured week data."""
    weeks = []
    # Split by week headers (## Week N: ...)
    parts = re.split(r'(?=##\s+Week\s+\d+)', md_content)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Extract week number and title
        header_match = re.match(r'##\s+Week\s+(\d+):?\s*(.*)', part)
        if not header_match:
            continue

        week_num = int(header_match.group(1))
        title = header_match.group(2).strip()

        # Extract objective
        obj_match = re.search(r'\*\*Objective:\*\*\s*(.*?)(?:\n|$)', part)
        objective = obj_match.group(1).strip() if obj_match else title

        # Extract resources
        resources = []
        res_matches = re.findall(r'[-*]\s+\*\*Resources?:\*\*\s*(.*?)(?:\n|$)', part)
        if res_matches:
            for r in res_matches:
                resources.extend([x.strip() for x in r.split(',') if x.strip()])

        # Extract project
        proj_match = re.search(r'\*\*Project:\*\*\s*(.*?)(?:\n|$)', part)
        project = proj_match.group(1).strip() if proj_match else ""

        # Extract success criteria
        sc_match = re.search(r'\*\*Success Criteria:\*\*\s*(.*?)(?:\n|$)', part)
        success_criteria = sc_match.group(1).strip() if sc_match else ""

        weeks.append({
            "week": week_num,
            "title": title,
            "objective": objective,
            "resources": resources,
            "project": project,
            "success_criteria": success_criteria,
            "content_md": part,
        })

    return weeks


def render_curriculum_html(md_content: str) -> str:
    """Convert curriculum markdown to styled HTML."""
    return markdown.markdown(md_content, extensions=["extra", "sane_lists"])

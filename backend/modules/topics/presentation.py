"""Deterministic presentation from an immutable, owner-derived snapshot."""

import html


def preference_fingerprint(preferences):
    return tuple(preferences.get(key) for key in ("languageId", "presentationLevelId", "timeZone"))


def render_presentation(name, items, preferences):
    language, level, zone = preference_fingerprint(preferences)
    if language not in ("en", "ko") or level != "standard" or not zone:
        raise ValueError("unsupported or unconfigured digest preferences")
    name = str(name)[:160]
    count = len(items)
    if language == "ko":
        heading = f"'{name}' 주제 다이제스트"
        description = f"최신 논문 {count}편입니다." if items else "새 소식이 없습니다."
        label = "표준 · 원문 제목 및 발행일"
    else:
        heading = f"'{name}' topic digest"
        description = f"{count} recent papers." if items else "No new papers in this window."
        label = "Standard · original titles and publication dates"
    lines = [
        f"- {str(item.get('title', ''))[:200]} ({item.get('publishedOn', '')})" for item in items
    ]
    rows = "".join(f"<li>{html.escape(line[2:], quote=True)}</li>" for line in lines)
    return {
        "subject": f"[DocSuri] {heading} ({count})",
        "text": "\n".join([heading, description, label, *lines]),
        "html": (
            f"<html><body><h3>{html.escape(heading)}</h3>"
            f"<p>{html.escape(description)}</p><p>{html.escape(label)}</p>"
            f"<ul>{rows}</ul></body></html>"
        ),
        "languageId": language,
        "presentationLevelId": level,
        "emptyLabel": "새 소식이 없습니다."
        if language == "ko"
        else "No new papers in this window.",
    }

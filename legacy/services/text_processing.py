import re

from tqdm import tqdm


def clean_texts(texts: list[str], tags: list[str], tag_patterns: dict[list[str]]) -> list[str]:
    """Cleans each text from all patterns specifieded by tag"""
    if not tag_patterns:
        return texts.copy()

    cleaned_texts = []
    for text, tag in tqdm(zip(texts, tags), desc="clean_texts", total=len(texts)):
        pattern = re.compile("|".join(map(re.escape, tag_patterns[tag])))
        cleaned_text = pattern.sub("", text)
        cleaned_texts.append(cleaned_text)

    return cleaned_texts

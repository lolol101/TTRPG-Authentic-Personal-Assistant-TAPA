import re

from tqdm import tqdm


def clean_texts(texts: list[str], patterns: list[str]) -> list[str]:
    """Cleans each text from all patterns"""
    if not patterns:
        return texts.copy()

    pattern = re.compile("|".join(map(re.escape, patterns)))

    cleaned_texts = []
    for text in tqdm(texts, desc="clean_texts"):
        cleaned_text = pattern.sub("", text)
        cleaned_texts.append(cleaned_text)

    return cleaned_texts

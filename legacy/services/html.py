from pathlib import Path

from bs4 import BeautifulSoup
from tqdm import tqdm


def load_html_files(path: str):
    """Loads all HTML files from the given directory and returns their names and data"""
    files_data = []
    root = Path(path)
    for path in tqdm(root.rglob("*.html"), desc="load_html_files"):
        file_name = path.name.split(".")[0]
        files_data.append((file_name, path.read_text(encoding="utf-8")))
    return files_data


def parse_html_data(arr_html_data: list[str]):
    """Parses html data (string format) and returns their texts"""
    texts = []
    for html_data in tqdm(arr_html_data, desc="parse_html_data"):
        soup = BeautifulSoup(html_data, "lxml")
        for tag in soup(["script", "style", "meta"]):
            tag.decompose()
        texts.append(soup.get_text(separator="\n", strip=True))

    return texts

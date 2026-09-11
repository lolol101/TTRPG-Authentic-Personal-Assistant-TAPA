from app.pipeline import chunk_sections, split_sections


def test_groups_text_under_the_heading_above_it() -> None:
    pages = ["The Six Abilities\nAll creatures have six abilities.\nThey measure traits."]

    assert split_sections(pages) == [
        ("The Six Abilities", "All creatures have six abilities. They measure traits.")
    ]


def test_drops_text_that_precedes_any_heading() -> None:
    """Filing stray text under a wrong title is worse than losing it."""
    pages = ["loose words before anything\nProficiency\nAdd your bonus."]

    assert split_sections(pages) == [("Proficiency", "Add your bonus.")]


def test_skips_table_of_contents_lines() -> None:
    pages = ["Contents\nPlaying the Game ...................5\nCombat .........12"]

    assert split_sections(pages) == []


def test_a_heading_needs_to_look_like_one() -> None:
    pages = ["Real Heading\nThis sentence, with commas, is not a heading.\nStill body text."]

    titles = [title for title, _ in split_sections(pages)]
    assert titles == ["Real Heading"]


def test_every_chunk_is_marked_as_dnd5e() -> None:
    chunks = chunk_sections([("Proficiency", "Add your proficiency bonus.")])

    assert [chunk.ruleset for chunk in chunks] == ["dnd5e"]
    assert chunks[0].source_book == "SRD 5.2.1"
    assert chunks[0].language == "en"


def test_chunk_text_carries_its_heading() -> None:
    """Retrieval matches on the chunk alone, so it has to say what it is about."""
    chunks = chunk_sections([("Grappling", "You can grab a creature.")])

    assert chunks[0].text == "Grappling. You can grab a creature."


def test_long_sections_split_on_sentences() -> None:
    body = " ".join(f"Sentence number {i} here." for i in range(60))

    chunks = chunk_sections([("Combat", body)], max_chars=200)

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 260 for chunk in chunks)


def test_repeated_headings_still_get_distinct_ids() -> None:
    """"Ability Descriptions" appears more than once in the SRD."""
    chunks = chunk_sections([("Ability Descriptions", "first"), ("Ability Descriptions", "second")])

    assert len({chunk.id for chunk in chunks}) == 2

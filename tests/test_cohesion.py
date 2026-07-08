"""Tests for the S202 semantic cohesion scoring pipeline."""

from __future__ import annotations

from okflint.cohesion import (
    Section,
    analyze_cohesion,
    build_similarity_matrix,
    compute_tfidf_vectors,
    find_components,
    merge_micro_sections,
    split_into_sections,
    tokenize,
)

MULTI = (
    "# Alpha\n\n"
    "This paragraph discusses cooking pasta with tomato sauce and basil "
    "leaves. The chef prepares pasta by boiling water, adding salt, and "
    "cooking the noodles until perfectly tender for dinner tonight.\n\n"
    "# Beta\n\n"
    "This paragraph discusses telescopes observing distant galaxies and "
    "stars. Astronomers use powerful telescopes to measure light from "
    "ancient galaxies across the vast universe every single night.\n"
)

SINGLE = (
    "# Alpha\n\n"
    "This paragraph discusses cooking pasta with tomato sauce and basil "
    "leaves in a warm kitchen every evening with friends and family "
    "gathered around the table for a long dinner.\n"
)


# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_lowercases_and_splits_on_non_alnum(self) -> None:
        assert tokenize("Cat, Dog! Bird?") == ["cat", "dog", "bird"]

    def test_drops_single_characters(self) -> None:
        assert tokenize("a cat I bird") == ["cat", "bird"]


# ---------------------------------------------------------------------------
# split_into_sections
# ---------------------------------------------------------------------------


class TestSplitIntoSections:
    def test_preamble_before_first_heading(self) -> None:
        body = "Some preamble text without heading.\n# Title\nBody content.\n"
        sections = split_into_sections(body)
        assert sections[0].title is None
        assert "preamble" in sections[0].body
        assert sections[1].title == "Title"

    def test_splits_at_each_heading_by_default(self) -> None:
        body = "# H1\nfirst\n## H2\nsecond\n"
        sections = split_into_sections(body)
        assert [s.title for s in sections] == [None, "H1", "H2"]
        assert [s.level for s in sections] == [None, 1, 2]

    def test_title_levels_filters_boundaries(self) -> None:
        body = "# H1\nfirst\n## H2\nsecond\n"
        sections = split_into_sections(body, title_levels={1})
        assert [s.title for s in sections] == [None, "H1"]
        assert "## H2" in sections[1].body


# ---------------------------------------------------------------------------
# merge_micro_sections
# ---------------------------------------------------------------------------


class TestMergeMicroSections:
    def test_no_merge_when_all_above_floor(self) -> None:
        sections = [
            Section(title=None, level=None, line=1, body="alpha beta gamma", token_count=10),
            Section(title="B", level=1, line=2, body="delta epsilon zeta", token_count=10),
        ]
        merged = merge_micro_sections(sections, min_tokens=5)
        assert [s.body for s in merged] == ["alpha beta gamma", "delta epsilon zeta"]

    def test_first_section_absorbed_into_next(self) -> None:
        sections = [
            Section(title=None, level=None, line=1, body="tiny", token_count=1),
            Section(title="B", level=1, line=2, body="second section body text", token_count=10),
        ]
        merged = merge_micro_sections(sections, min_tokens=5)
        assert len(merged) == 1
        assert merged[0].title == "B"
        assert "tiny" in merged[0].body
        assert "second section body text" in merged[0].body

    def test_middle_section_absorbed_into_previous(self) -> None:
        sections = [
            Section(title="A", level=1, line=1, body="first section body words", token_count=10),
            Section(title="B", level=2, line=2, body="micro filler", token_count=1),
            Section(title="C", level=1, line=3, body="third section body words", token_count=10),
        ]
        merged = merge_micro_sections(sections, min_tokens=5)
        assert [s.title for s in merged] == ["A", "C"]
        assert "micro filler" in merged[0].body


# ---------------------------------------------------------------------------
# compute_tfidf_vectors
# ---------------------------------------------------------------------------


class TestComputeTfidfVectors:
    def test_term_shared_by_every_document_gets_zero_weight(self) -> None:
        vectors = compute_tfidf_vectors(["cat dog", "cat dog"])
        assert vectors[0]["cat"] == 0.0
        assert vectors[0]["dog"] == 0.0

    def test_term_unique_to_one_document_gets_nonzero_weight(self) -> None:
        vectors = compute_tfidf_vectors(["cat cat dog", "cat cat dog", "bird fish"])
        assert vectors[0]["cat"] > 0.0
        assert vectors[2]["bird"] > 0.0


# ---------------------------------------------------------------------------
# build_similarity_matrix
# ---------------------------------------------------------------------------


class TestBuildSimilarityMatrix:
    def test_diagonal_is_one(self) -> None:
        vectors = compute_tfidf_vectors(["cat cat dog", "cat cat dog", "bird fish"])
        matrix = build_similarity_matrix(vectors)
        assert matrix[0][0] == 1.0
        assert matrix[1][1] == 1.0
        assert matrix[2][2] == 1.0

    def test_identical_documents_are_maximally_similar(self) -> None:
        vectors = compute_tfidf_vectors(["cat cat dog", "cat cat dog", "bird fish"])
        matrix = build_similarity_matrix(vectors)
        assert matrix[0][1] == 1.0
        assert matrix[1][0] == 1.0

    def test_disjoint_documents_have_zero_similarity(self) -> None:
        vectors = compute_tfidf_vectors(["cat cat dog", "cat cat dog", "bird fish"])
        matrix = build_similarity_matrix(vectors)
        assert matrix[0][2] == 0.0


# ---------------------------------------------------------------------------
# find_components
# ---------------------------------------------------------------------------


class TestFindComponents:
    def test_linked_pair_forms_one_component(self) -> None:
        matrix = [
            [1.0, 0.5, 0.0],
            [0.5, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
        assert find_components(matrix, tau=0.15) == [[0, 1], [2]]

    def test_higher_tau_splits_all_into_singletons(self) -> None:
        matrix = [
            [1.0, 0.5, 0.0],
            [0.5, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
        assert find_components(matrix, tau=0.6) == [[0], [1], [2]]

    def test_all_linked_forms_single_component(self) -> None:
        matrix = [
            [1.0, 0.5, 0.5],
            [0.5, 1.0, 0.5],
            [0.5, 0.5, 1.0],
        ]
        assert find_components(matrix, tau=0.15) == [[0, 1, 2]]


# ---------------------------------------------------------------------------
# analyze_cohesion (end-to-end)
# ---------------------------------------------------------------------------


class TestAnalyzeCohesion:
    def test_multi_cluster_document_yields_two_components(self) -> None:
        result = analyze_cohesion(MULTI, tau=0.15)
        assert len(result.sections) == 2
        assert len(result.components) == 2

    def test_single_cluster_document_yields_one_component(self) -> None:
        result = analyze_cohesion(SINGLE, tau=0.15)
        assert len(result.sections) == 1
        assert len(result.components) == 1

    def test_frontmatter_is_stripped_before_analysis(self) -> None:
        content = "---\ntype: Note\n---\n" + SINGLE
        result = analyze_cohesion(content, tau=0.15)
        assert len(result.sections) == 1

    def test_heading_inside_code_fence_is_not_a_section_boundary(self) -> None:
        content = (
            "# Real\n"
            "some real content about telescopes and stars for testing "
            "purposes today.\n"
            "```\n# Fake\n```\n"
            "more telescope text here.\n"
        )
        result = analyze_cohesion(content, tau=0.15)
        assert len(result.sections) == 1
        assert result.sections[0].title == "Real"
        assert "fake" not in result.sections[0].body.lower()

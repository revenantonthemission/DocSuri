"""Source fidelity and finite parsing controls through the retained parser."""

from datetime import UTC, datetime

import pytest

from backend.modules.corpus.source_parser import parse_source

pytestmark = pytest.mark.u1_component
DATE = datetime(2026, 10, 11, tzinfo=UTC)


def parse(body):
    return parse_source(
        body.encode(),
        paper="synthetic-parser",
        version=1,
        title="Parser diagnostic",
        fetched_at=DATE,
    )


def test_inline_and_display_math_keep_literal_meaning_and_section_anchor():
    model, chunks = parse(r"""<article class="ltx_document"><section class="ltx_section">
    <h2>3 Attention</h2><p class="ltx_p">Divide by <math alttext="\sqrt{d_k}"><mi>x</mi></math>.</p>
    <table class="ltx_equation"><tr><td><math alttext="\operatorname{softmax}(QK^T/\sqrt{d_k})V">
    <mi>x</mi></math></td></tr></table></section></article>""")
    assert r"\sqrt{d_k}" in chunks[0]["text"]
    assert chunks[1]["text"] == r"\operatorname{softmax}(QK^T/\sqrt{d_k})V"
    assert chunks[1]["anchor"] == "s1.eq1"
    assert chunks[1]["section"] == "3 Attention"
    assert model["meta"]["paperId"] == "synthetic-parser"


def test_nested_sections_have_stable_ids_and_repeatable_content():
    html = """<section class="ltx_section"><h2>2 Methods</h2><section class="ltx_subsection">
    <h3>2.1 Variant</h3><p class="ltx_p">An authored diagnostic.</p></section></section>"""
    first = parse(html)
    assert first == parse(html)
    assert first[1][0]["anchor"] == "s1.1.p1"
    assert first[1][0]["section"] == "2 Methods / 2.1 Variant"


def test_active_elements_are_not_returned_as_research_text():
    _, chunks = parse("""<p class="ltx_p">Usable evidence.</p><script>secretInstruction()</script>
    <iframe>hidden instruction</iframe><style>body{display:none}</style>""")
    assert [c["text"] for c in chunks] == ["Usable evidence."]


def test_figure_caption_preserves_reference_without_claiming_pixels():
    model, chunks = parse("""<figure class="ltx_figure"><img src="https://untrusted.invalid/a.png">
    <figcaption class="ltx_caption">Figure 1: An authored diagram caption.</figcaption></figure>""")
    assert "authored diagram" in chunks[0]["text"]
    assert model["sections"][0]["blocks"][0]["assetRef"]["assetId"].startswith("synthetic-parser:")
    assert "untrusted.invalid" not in str(model)


def test_oversized_deep_and_empty_inputs_reject_without_truncation():
    for source in ("x" * 2097153, "<div>" * 129, "<script>only active text</script>", "\0"):
        with pytest.raises(ValueError):
            parse(source)


def test_projection_bound_and_large_paragraph_require_explicit_policy():
    with pytest.raises(ValueError, match="chunk allocation"):
        parse('<p class="ltx_p">Diagnostic.</p>' * 257)
    with pytest.raises(ValueError, match="chunking policy"):
        parse('<p class="ltx_p">' + "word " * 2000 + "</p>")


def test_svg_object_figure_retains_caption_after_active_content_removal():
    # The P2 Figure 1 structure, with newly authored diagnostic text.
    model, chunks = parse("""<section class="ltx_section" id="S1"><h2>Introduction</h2>
    <figure class="ltx_figure" id="S1.F1"><object type="image/svg+xml"
    data="untrusted.svg"></object><figcaption class="ltx_caption">
    <span class="ltx_tag ltx_tag_figure">Figure 1: </span>Diagnostic retrieval chooses
    top-K records; the generator marginalizes document choices.</figcaption></figure>
    </section>""")
    assert len(chunks) == 1 and chunks[0]["kind"] == "figure"
    assert chunks[0]["anchor"] == "s1.fig1"
    assert "top-K" in chunks[0]["text"] and "marginalizes" in chunks[0]["text"]
    figure = model["sections"][0]["blocks"][0]
    assert figure["anchorLabel"] == "Figure 1"
    assert "untrusted.svg" not in str(model)

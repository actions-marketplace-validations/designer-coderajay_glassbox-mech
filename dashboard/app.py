"""Glassbox HuggingFace Space: explain a transformer's prediction and measure faithfulness.

Deployed by ``.github/workflows/deploy_hf.yml`` together with ``space_ui.py`` (copy,
CSS and HTML renderers) and ``v7_investigation.py`` (investigation tab).

Design rules for this file:
* The model is loaded once. All model-backed events share one queue slot
  (``concurrency_id="model"``) because TransformerLens hooks are not thread-safe.
* Every handler returns a readable message instead of raising.
* No prompts or results are logged or stored beyond temporary download files.
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
import space_ui as ui
import torch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("glassbox.space")
# The library logs every trace file at INFO; keep the Space logs readable.
for _name in ("glassbox", "httpx"):
    logging.getLogger(_name).setLevel(logging.WARNING)
log.setLevel(logging.INFO)

# ── Model (loaded once at startup) ────────────────────────────────────────────
MODEL: Any = None
GB: Any = None
STARTUP_ERROR: Optional[str] = None

try:
    _t0 = time.time()
    from transformer_lens import HookedTransformer

    from glassbox import GlassboxV2

    MODEL = HookedTransformer.from_pretrained("gpt2", device="cpu")
    MODEL.eval()
    GB = GlassboxV2(MODEL)
    log.info("model ready in %.1fs", time.time() - _t0)
except Exception:  # noqa: BLE001 - surface any startup failure in the UI
    STARTUP_ERROR = traceback.format_exc()
    log.error("startup failed:\n%s", STARTUP_ERROR)

OUT_DIR = Path(tempfile.gettempdir()) / "glassbox_space"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FILE_TTL_S = 2 * 3600
MODEL_QUEUE = {"concurrency_id": "model", "concurrency_limit": 1}
NOT_READY = (
    "The model is not loaded, so this cannot run right now. Please try again in a "
    "minute; if it persists, the Space owner has been shown the error in the logs."
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _jsonable(obj: Any) -> Any:
    """Convert tuples, numpy and torch values to JSON-safe Python types."""
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "item") and callable(obj.item):
        try:
            return obj.item()
        except (ValueError, RuntimeError):
            pass
    if hasattr(obj, "tolist"):
        return obj.tolist()
    return obj


def _write_download(payload: Dict[str, Any], stem: str) -> str:
    """Write a temporary JSON download and prune old ones."""
    cutoff = time.time() - FILE_TTL_S
    for old in OUT_DIR.glob("*.json"):
        try:
            if old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:
            continue
    path = OUT_DIR / f"{stem}-{uuid.uuid4().hex[:8]}.json"
    path.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")
    return str(path)


def _single_token(token: str) -> int:
    """Token id for ``token``; raises ValueError if it is not exactly one token."""
    ids = MODEL.to_tokens(token, prepend_bos=False)[0]
    if ids.numel() != 1:
        raise ValueError(
            f"{token!r} is {ids.numel()} tokens for GPT-2. Use a single token, "
            "usually a word with its leading space, e.g. ' Paris'."
        )
    return int(ids[0])


def _fail(exc: Exception) -> str:
    log.warning(
        "handler error: %s", "".join(traceback.format_exception_only(exc)).strip()
    )
    if isinstance(exc, ValueError):
        return ui.message_html(str(exc), "error")
    return ui.message_html(
        f"Something went wrong ({type(exc).__name__}). Try a shorter prompt or a "
        "different pair of tokens.",
        "error",
    )


# ── Tab 1: explain a prediction ──────────────────────────────────────────────
EXPLAIN_EMPTY = ui.empty_state_html(
    "Your results will appear here",
    "Pick an example on the left or write your own prompt, then press Explain.",
)


def explain_prediction(
    prompt: str, correct: str, incorrect: str
) -> Tuple[str, str, str, str, Optional[str]]:
    """Circuit + faithfulness for one prompt. Returns 4 HTML blocks and a file."""
    if GB is None:
        return ui.message_html(NOT_READY, "error"), "", "", "", None
    err = ui.validate_inputs(prompt, correct, incorrect)
    if err:
        return ui.message_html(err, "warn"), "", "", "", None
    try:
        _single_token(correct)
        _single_token(incorrect)
        result = GB.analyze(prompt.strip(), correct, incorrect)
        text = ui.summary_text(result, correct, incorrect)
    except Exception as exc:  # noqa: BLE001
        return _fail(exc), "", "", "", None
    file = _write_download(
        {
            "glassbox_version": ui.VERSION,
            "model": "gpt2",
            "prompt": prompt.strip(),
            "correct": correct,
            "incorrect": incorrect,
            "result": result,
        },
        "glassbox-analysis",
    )
    return (
        ui.metric_cards_html(result),
        ui.head_grid_html(result["attributions"], result["circuit"]),
        ui.explanation_html(text, result.get("evidence_tier")),
        ui.circuit_table_html(result),
        file,
    )


# ── Tab 2: logit lens ─────────────────────────────────────────────────────────
def logit_lens(prompt: str, token: str) -> str:
    """Probability and rank of ``token`` decoded after every layer."""
    if MODEL is None:
        return ui.message_html(NOT_READY, "error")
    if not (prompt or "").strip() or not token:
        return ui.message_html("Enter a prompt and a token.", "warn")
    if len(prompt) > ui.MAX_PROMPT_CHARS:
        return ui.message_html("Please use a shorter prompt.", "warn")
    try:
        t_idx = _single_token(token)
        tokens = MODEL.to_tokens(prompt.strip())
        rows: List[Tuple[int, float, int]] = []
        with torch.no_grad():
            _, cache = MODEL.run_with_cache(tokens)
            for layer in range(MODEL.cfg.n_layers):
                resid = cache[f"blocks.{layer}.hook_resid_post"][0, -1]
                logits = MODEL.unembed(MODEL.ln_final(resid[None, None]))[0, 0]
                prob = torch.softmax(logits, dim=-1)[t_idx].item()
                rank = int((logits > logits[t_idx]).sum().item()) + 1
                rows.append((layer, prob, rank))
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)
    return ui.logit_lens_html(rows, token)


# ── Tab 3: attention ──────────────────────────────────────────────────────────
def attention(prompt: str, layer: float, head: float) -> str:
    """Attention pattern of one head."""
    if MODEL is None:
        return ui.message_html(NOT_READY, "error")
    if not (prompt or "").strip():
        return ui.message_html("Enter a prompt.", "warn")
    try:
        tokens = MODEL.to_tokens(prompt.strip())
        if tokens.shape[1] > ui.MAX_ATTENTION_TOKENS:
            raise ValueError(
                f"That prompt is {tokens.shape[1]} tokens; please keep it under "
                f"{ui.MAX_ATTENTION_TOKENS} so the map stays readable."
            )
        with torch.no_grad():
            _, cache = MODEL.run_with_cache(tokens)
        pattern = cache[f"blocks.{int(layer)}.attn.hook_pattern"][0, int(head)]
        strs = MODEL.to_str_tokens(tokens[0])
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)
    return ui.attention_html(strs, pattern.tolist(), int(layer), int(head))


# ── Tab 5: Annex IV draft ─────────────────────────────────────────────────────
CONTEXTS: Dict[str, str] = {
    "Financial services (e.g. credit)": "FINANCIAL_SERVICES",
    "Employment / HR": "HR_EMPLOYMENT",
    "Education": "EDUCATION",
    "Healthcare": "HEALTHCARE",
    "Legal": "LEGAL",
    "Other high-risk use": "OTHER_HIGH_RISK",
}


def annex_draft(
    prompt: str,
    correct: str,
    incorrect: str,
    system: str,
    provider: str,
    context: str,
) -> Tuple[str, str, Optional[str]]:
    """Analysis + Annex IV draft. Returns cards HTML, sections HTML and a JSON file."""
    if GB is None:
        return ui.message_html(NOT_READY, "error"), "", None
    err = ui.validate_inputs(prompt, correct, incorrect)
    if err:
        return ui.message_html(err, "warn"), "", None
    try:
        from glassbox import AnnexIVReport, DeploymentContext

        _single_token(correct)
        _single_token(incorrect)
        result = GB.analyze(prompt.strip(), correct, incorrect)
        report = AnnexIVReport(
            model_name=(system or "GPT-2 small").strip()[:120],
            system_purpose=f"Demonstration: {prompt.strip()[:100]}",
            provider_name=(provider or "Demo organisation").strip()[:120],
            provider_address="[PROVIDER TO COMPLETE — registered address]",
            deployment_context=getattr(
                DeploymentContext, CONTEXTS.get(context, "OTHER_HIGH_RISK")
            ),
        )
        report.add_analysis(result, use_case=f"Demo prompt: {prompt.strip()[:60]}")
        doc = json.loads(report.to_json())
    except Exception as exc:  # noqa: BLE001
        return _fail(exc), "", None
    file = _write_download(doc, "glassbox-annex-iv-draft")
    return ui.metric_cards_html(result), ui.annex_sections_html(doc["sections"]), file


# ── UI ────────────────────────────────────────────────────────────────────────
RUST = gr.themes.Color(
    c50="#fbf3ef",
    c100="#f6e2d9",
    c200="#ecc2b1",
    c300="#e09e85",
    c400="#d27a5b",
    c500="#b85c38",
    c600="#9d4b2c",
    c700="#803d25",
    c800="#66321f",
    c900="#4f281a",
    c950="#2b150d",
    name="rust",
)
THEME = gr.themes.Base(
    primary_hue=RUST,
    neutral_hue="stone",
    radius_size="lg",
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "monospace"],
).set(
    body_background_fill="#fbfaf8",
    body_background_fill_dark="#0f0f12",
    body_text_color="#1c1917",
    body_text_color_dark="#f3f0eb",
    background_fill_primary="#ffffff",
    background_fill_primary_dark="#17171b",
    background_fill_secondary="#f7f5f2",
    background_fill_secondary_dark="#1e1e23",
    block_background_fill="#ffffff",
    block_background_fill_dark="#17171b",
    block_border_color="rgba(28,25,23,0.10)",
    block_border_color_dark="rgba(255,255,255,0.10)",
    border_color_primary="rgba(28,25,23,0.12)",
    border_color_primary_dark="rgba(255,255,255,0.12)",
    block_label_text_color="#6b645d",
    block_label_text_color_dark="#a8a29b",
    input_background_fill="#ffffff",
    input_background_fill_dark="#1e1e23",
    button_primary_background_fill="#b85c38",
    button_primary_background_fill_hover="#9d4b2c",
    button_primary_background_fill_dark="#e2825c",
    button_primary_background_fill_hover_dark="#ec9573",
    button_primary_text_color="#ffffff",
    button_primary_text_color_dark="#1a0f0a",
    button_large_text_weight="600",
    shadow_drop="none",
    shadow_drop_lg="none",
    block_shadow="none",
    block_shadow_dark="none",
)
HEAD = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif&display=swap"'
    ' rel="stylesheet">'
    '<meta name="description" content="Glassbox: find the attention heads that drive a '
    "transformer's prediction and measure how faithful that explanation is.\">"
)
DEFAULT = ui.EXAMPLES[0]

with gr.Blocks(
    theme=THEME,
    css=ui.CSS,
    head=HEAD,
    title="Glassbox: explain and measure a transformer's prediction",
    analytics_enabled=False,
    delete_cache=(3600, FILE_TTL_S),
) as demo:
    gr.HTML(
        ui.header_html("ready" if STARTUP_ERROR is None else "error"),
        padding=False,
    )
    if STARTUP_ERROR:
        gr.HTML(
            ui.message_html(
                "The model failed to load, so the tools below are unavailable. "
                "The full error is in the Space logs.",
                "error",
            )
        )

    with gr.Tabs():
        # 1 ── Explain a prediction
        with gr.Tab("Explain a prediction", id="explain"):
            gr.HTML(f'<p class="gb-intro">{ui.esc(ui.INTRO_EXPLAIN)}</p>')
            with gr.Row(equal_height=False):
                with gr.Column(scale=4, min_width=300):
                    ex_prompt = gr.Textbox(
                        label="Prompt", value=DEFAULT[0], lines=3, max_lines=6
                    )
                    with gr.Row():
                        ex_correct = gr.Textbox(
                            label="Expected next token", value=DEFAULT[1]
                        )
                        ex_incorrect = gr.Textbox(
                            label="Alternative token", value=DEFAULT[2]
                        )
                    ex_btn = gr.Button(
                        "Explain prediction", variant="primary", size="lg"
                    )
                    ex_file = gr.File(
                        label="Download full result (JSON)", interactive=False
                    )
                with gr.Column(scale=7, min_width=360):
                    ex_cards = gr.HTML(EXPLAIN_EMPTY)
                    ex_grid = gr.HTML()
                    with gr.Row(equal_height=False):
                        ex_text = gr.HTML()
                        ex_table = gr.HTML()
            ex_outputs = [ex_cards, ex_grid, ex_text, ex_table, ex_file]
            ex_btn.click(
                explain_prediction,
                [ex_prompt, ex_correct, ex_incorrect],
                ex_outputs,
                api_name="explain",
                **MODEL_QUEUE,
            )
            gr.Examples(
                examples=[list(e) for e in ui.EXAMPLES],
                example_labels=ui.EXAMPLE_LABELS,
                inputs=[ex_prompt, ex_correct, ex_incorrect],
                outputs=ex_outputs,
                fn=explain_prediction,
                cache_examples=STARTUP_ERROR is None,
                cache_mode="lazy",
                label="Try an example",
            )

        # 2 ── Logit lens
        with gr.Tab("Layer by layer", id="lens"):
            gr.HTML(f'<p class="gb-intro">{ui.esc(ui.INTRO_LENS)}</p>')
            with gr.Row(equal_height=False):
                with gr.Column(scale=4, min_width=300):
                    ll_prompt = gr.Textbox(label="Prompt", value=DEFAULT[0], lines=3)
                    ll_token = gr.Textbox(label="Token to track", value=DEFAULT[1])
                    ll_btn = gr.Button("Trace through layers", variant="primary")
                with gr.Column(scale=7, min_width=360):
                    ll_out = gr.HTML(
                        ui.empty_state_html(
                            "Layer-by-layer view",
                            "Shows how the probability of your token grows through "
                            "GPT-2's 12 layers.",
                        )
                    )
            ll_btn.click(
                logit_lens,
                [ll_prompt, ll_token],
                ll_out,
                api_name="logit_lens",
                **MODEL_QUEUE,
            )

        # 3 ── Attention
        with gr.Tab("Attention", id="attention"):
            gr.HTML(f'<p class="gb-intro">{ui.esc(ui.INTRO_ATTENTION)}</p>')
            with gr.Row(equal_height=False):
                with gr.Column(scale=4, min_width=300):
                    at_prompt = gr.Textbox(label="Prompt", value=DEFAULT[0], lines=3)
                    with gr.Row():
                        at_layer = gr.Slider(0, 11, value=9, step=1, label="Layer")
                        at_head = gr.Slider(0, 11, value=9, step=1, label="Head")
                    at_btn = gr.Button("Show attention", variant="primary")
                with gr.Column(scale=7, min_width=360):
                    at_out = gr.HTML(
                        ui.empty_state_html(
                            "Attention map",
                            "Each row is a token; darker cells are the earlier tokens "
                            "it attends to.",
                        )
                    )
            at_btn.click(
                attention,
                [at_prompt, at_layer, at_head],
                at_out,
                api_name="attention",
                **MODEL_QUEUE,
            )

        # 4 ── Investigation layer
        with gr.Tab("Investigate a change", id="investigate"):
            gr.HTML(
                '<p class="gb-intro">An AI system started behaving differently after '
                "several changes. Which change mattered? Two worked examples: a "
                "simulated tool-using agent (instant, true effects shown) and a RAG "
                "assistant on GPT-2.</p>"
            )
            with gr.Tabs():
                with gr.Tab("Agent trajectory (simulated)", id="investigate_agent"):
                    try:
                        from v7_agent_demo import build_tab as build_agent_tab
                    except ImportError as exc:
                        gr.HTML(ui.message_html(f"Unavailable: {exc}", "error"))
                    else:
                        build_agent_tab(
                            gr,
                            api_name="investigate_agent",
                            concurrency_id="agent",
                            concurrency_limit=2,
                        )
                with gr.Tab("RAG assistant (GPT-2)", id="investigate_rag"):
                    try:
                        from v7_investigation import build_tab
                    except ImportError as exc:
                        gr.HTML(
                            ui.message_html(
                                "This tab needs glassbox with glassbox.v7 installed "
                                f"({exc}).",
                                "error",
                            )
                        )
                    else:
                        build_tab(gr, api_name="investigate", **MODEL_QUEUE)

        # 5 ── Annex IV draft
        with gr.Tab("Annex IV draft", id="annex"):
            gr.HTML(f'<p class="gb-intro">{ui.esc(ui.INTRO_ANNEX)}</p>')
            with gr.Row(equal_height=False):
                with gr.Column(scale=4, min_width=300):
                    ax_prompt = gr.Textbox(label="Prompt", value=DEFAULT[0], lines=3)
                    with gr.Row():
                        ax_correct = gr.Textbox(
                            label="Expected token", value=DEFAULT[1]
                        )
                        ax_incorrect = gr.Textbox(
                            label="Alternative token", value=DEFAULT[2]
                        )
                    ax_system = gr.Textbox(
                        label="AI system name", value="GPT-2 small (demo)"
                    )
                    ax_provider = gr.Textbox(
                        label="Provider", value="Demo organisation"
                    )
                    ax_context = gr.Dropdown(
                        list(CONTEXTS),
                        value="Other high-risk use",
                        label="Deployment context",
                    )
                    ax_btn = gr.Button("Draft Annex IV evidence", variant="primary")
                    ax_file = gr.File(label="Download draft (JSON)", interactive=False)
                with gr.Column(scale=7, min_width=360):
                    ax_cards = gr.HTML(
                        ui.empty_state_html(
                            "Annex IV draft",
                            "See which sections Glassbox can fill from evidence and "
                            "which need your input.",
                        )
                    )
                    ax_sections = gr.HTML()
            ax_btn.click(
                annex_draft,
                [
                    ax_prompt,
                    ax_correct,
                    ax_incorrect,
                    ax_system,
                    ax_provider,
                    ax_context,
                ],
                [ax_cards, ax_sections, ax_file],
                api_name="annex_iv_draft",
                **MODEL_QUEUE,
            )

        # 6 ── About
        with gr.Tab("About & limits", id="about"):
            gr.Markdown(ui.ABOUT_MD)

    gr.HTML(ui.FOOTER_HTML, padding=False)

demo.queue(max_size=24, default_concurrency_limit=1)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, ssr_mode=False)

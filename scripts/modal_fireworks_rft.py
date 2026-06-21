"""Launch Cologic Fireworks RFT from Modal.

The Fireworks API key is read from the Modal secret named `fireworks-api`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import modal

app = modal.App("rl-hdl-fireworks-rft")

METHOD_ALIASES = {
    "grpo": "GRPO",
    "dapo": "DAPO",
    "dpo": "DPO",
    "orpo": "ORPO",
    "gspo-token": "GSPO_TOKEN",
    "gspo_token": "GSPO_TOKEN",
}

launcher_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("build-essential", "ca-certificates", "verilator")
    .pip_install("eval-protocol>=0.3.31", "pytest>=8")
    .add_local_python_source("cologic")
    .add_local_dir("fireworks_rft", remote_path="/root/fireworks_rft")
)


def _copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    print("+ " + " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=cwd, env=merged_env, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end="", flush=True)
    if proc.stderr:
        print(proc.stderr, end="", flush=True)
    if check and proc.returncode:
        raise RuntimeError(f"command failed with exit {proc.returncode}: {' '.join(cmd)}")
    return proc


def _normalize_output_model(output_model: str, account: str) -> str:
    if output_model.startswith("accounts/"):
        return output_model
    account = account or os.environ.get("FIREWORKS_ACCOUNT_ID", "")
    if account:
        return f"accounts/{account}/models/{output_model}"
    return output_model


def _assemble(workdir: Path, split: str, max_rows: int | None) -> Path:
    import cologic
    from cologic.rft import rows_for_task_ids, split_task_ids, write_jsonl

    upload_dir = workdir / "cologic_fireworks_rft"
    template_dir = Path("/root/fireworks_rft")
    _copytree(template_dir, upload_dir)

    package_dir = Path(cologic.__file__).resolve().parent
    _copytree(package_dir, upload_dir / "cologic")

    task_ids = split_task_ids(split)
    if max_rows:
        task_ids = task_ids[:max_rows]
    write_jsonl(rows_for_task_ids(task_ids), upload_dir / "dataset.jsonl")
    write_jsonl(rows_for_task_ids(task_ids[: min(2, len(task_ids))], include_golden=True), upload_dir / "smoke_dataset.jsonl")

    manifest = {
        "split": split,
        "rows": len(task_ids),
        "task_ids": task_ids,
        "upload_dir": str(upload_dir),
    }
    (upload_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)
    return upload_dir


@app.function(
    image=launcher_image,
    secrets=[modal.Secret.from_name("fireworks-api")],
    timeout=3600,
)
def launch_remote(
    base_model: str,
    output_model: str,
    account: str,
    split: str,
    max_rows: int | None,
    dry_run: bool,
    force: bool,
    skip_validation: bool,
    skip_smoke: bool,
    epochs: int,
    learning_rate: float,
    lora_rank: int,
    batch_size_samples: int,
    chunk_size: int,
    max_output_tokens: int,
    temperature: float,
    max_concurrent_rollouts: int,
    max_concurrent_evaluations: int,
    method: str,
) -> dict:
    workdir = Path("/tmp/cologic-rft")
    upload_dir = _assemble(workdir, split, max_rows)
    output_model = _normalize_output_model(output_model, account)

    if not skip_smoke:
        smoke_env = {
            "EP_USE_NO_OP_ROLLOUT_PROCESSOR": "1",
            "EP_JSONL_PATH": str(upload_dir / "smoke_dataset.jsonl"),
            "EP_MAX_DATASET_ROWS": "2",
            "COLOGIC_RFT_MAX_DATASET_ROWS": "2",
            "COLOGIC_RFT_ROLLOUT_MODEL": base_model,
            "COLOGIC_RFT_MAX_OUTPUT_TOKENS": str(max_output_tokens),
        }
        _run(["pytest", "-q", "test_cologic_reward.py"], cwd=upload_dir, env=smoke_env)

    cmd = [
        "eval-protocol",
        "create",
        "rft",
        "--yes",
        "--base-model",
        base_model,
        "--output-model",
        output_model,
        "--epochs",
        str(epochs),
        "--learning-rate",
        str(learning_rate),
        "--lora-rank",
        str(lora_rank),
        "--batch-size-samples",
        str(batch_size_samples),
        "--chunk-size",
        str(chunk_size),
        "--max-output-tokens",
        str(max_output_tokens),
        "--temperature",
        str(temperature),
        "--max-concurrent-rollouts",
        str(max_concurrent_rollouts),
        "--max-concurrent-evaluations",
        str(max_concurrent_evaluations),
    ]
    if method:
        method = METHOD_ALIASES.get(method.lower(), method)
        cmd.extend(["--method", method])
    if force:
        cmd.append("--force")
    if skip_validation:
        cmd.append("--skip-validation")
    if dry_run:
        cmd.append("--dry-run")

    env = {
        "COLOGIC_RFT_ROLLOUT_MODEL": base_model,
        "COLOGIC_RFT_MAX_OUTPUT_TOKENS": str(max_output_tokens),
    }
    proc = _run(cmd, cwd=upload_dir, env=env, check=not dry_run)
    return {
        "upload_dir": str(upload_dir),
        "dry_run": dry_run,
        "output_model": output_model,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


@app.function(
    image=launcher_image,
    secrets=[modal.Secret.from_name("fireworks-api")],
    timeout=120,
)
def status_remote(job_id: str, account: str) -> dict:
    from fireworks import Fireworks

    client = Fireworks(account_id=account or None)
    job = client.reinforcement_fine_tuning_jobs.get(job_id, account_id=account or None)
    data = job.model_dump(mode="json", by_alias=True, exclude_none=True)
    progress = data.get("jobProgress") or {}
    return {
        "name": data.get("name"),
        "state": data.get("state"),
        "output_model": (data.get("trainingConfig") or {}).get("outputModel"),
        "dataset": data.get("dataset"),
        "evaluator": data.get("evaluator"),
        "progress": progress,
        "dashboard": f"https://app.fireworks.ai/dashboard/fine-tuning/reinforcement/{job_id}",
    }


@app.local_entrypoint()
def launch(
    base_model: str = "accounts/fireworks/models/gemma-4-26b-a4b-it",
    output_model: str = "cologic-gemma-rtl-rft",
    account: str = "",
    split: str = "rft",
    max_rows: int = 0,
    dry_run: bool = False,
    force: bool = False,
    skip_validation: bool = True,
    skip_smoke: bool = False,
    epochs: int = 1,
    learning_rate: float = 1e-5,
    lora_rank: int = 16,
    batch_size_samples: int = 2,
    chunk_size: int = 10,
    max_output_tokens: int = 2048,
    temperature: float = 0.7,
    max_concurrent_rollouts: int = 4,
    max_concurrent_evaluations: int = 4,
    method: str = "",
):
    """Assemble, smoke-test, and launch the Fireworks RFT job."""
    result = launch_remote.remote(
        base_model=base_model,
        output_model=output_model,
        account=account,
        split=split,
        max_rows=max_rows or None,
        dry_run=dry_run,
        force=force,
        skip_validation=skip_validation,
        skip_smoke=skip_smoke,
        epochs=epochs,
        learning_rate=learning_rate,
        lora_rank=lora_rank,
        batch_size_samples=batch_size_samples,
        chunk_size=chunk_size,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        max_concurrent_rollouts=max_concurrent_rollouts,
        max_concurrent_evaluations=max_concurrent_evaluations,
        method=method,
    )
    print(json.dumps(result, indent=2))


@app.local_entrypoint()
def status(job_id: str, account: str = ""):
    """Print Fireworks RFT job state/progress."""
    print(json.dumps(status_remote.remote(job_id, account), indent=2))

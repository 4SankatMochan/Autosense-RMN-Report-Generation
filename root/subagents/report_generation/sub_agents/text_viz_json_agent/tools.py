from google.cloud import storage
import base64
import json
import re
import pathlib
from collections import defaultdict
from typing import List, Optional
import os
from google.adk.tools import ToolContext


def _upload_local_artifacts_to_gcs(session_id: str, bucket_name: str, user_id: str = "user") -> dict:
    """
    Fallback for when adk web uses local file artifact service instead of GCS.
    Scans .adk/artifacts for the session, uploads PNGs/JSONs/txts to GCS at the
    same path prefix that the main GCS-scan branch expects, then returns a
    result_data dict in the same format so the rest of the pipeline is unchanged.

    ADK local store layout:
      artifacts/{art_name}/versions/{version}/metadata.json   ← skipped
      artifacts/{art_name}/versions/{version}/{art_name}      ← content
    """
    cwd = pathlib.Path(os.getcwd())
    local_root = cwd / ".adk" / "artifacts" / "users" / user_id / "sessions" / session_id / "artifacts"
    print(f"[local-fallback] session_id={session_id!r}, looking at: {local_root}")

    if not local_root.exists():
        print(f"[local-fallback] Artifact dir not found: {local_root}")
        # Scan all available sessions and pick the most recently-modified one with artifacts
        sessions_root = cwd / ".adk" / "artifacts" / "users" / user_id / "sessions"
        print(f"[local-fallback] Scanning all sessions under: {sessions_root}")
        best_root = None
        best_mtime = 0.0
        if sessions_root.exists():
            for session_dir in sessions_root.iterdir():
                if not session_dir.is_dir():
                    continue
                art_dir = session_dir / "artifacts"
                if not art_dir.exists():
                    continue
                file_list = [f for f in art_dir.rglob("*") if f.is_file()]
                if not file_list:
                    continue
                mtime = max(f.stat().st_mtime for f in file_list)
                if mtime > best_mtime:
                    best_mtime = mtime
                    best_root = art_dir
        if best_root:
            print(f"[local-fallback] Falling back to most-recent session: {best_root.parent.name}")
            local_root = best_root
        else:
            print("[local-fallback] No session directories with artifacts found.")
            return {}

    versioned_pat = re.compile(r'^(.+)/versions/(\d+)/(.+)$')
    # art_name → list of (version_int, content_filepath); metadata.json is excluded
    artifact_versions: dict = defaultdict(list)

    for fp in local_root.rglob("*"):
        if not fp.is_file():
            continue
        rel = fp.relative_to(local_root).as_posix()
        m = versioned_pat.match(rel)
        if not m:
            continue
        # m.group(3) is the filename inside the version directory.
        # Skip ADK's own metadata sidecar files.
        if m.group(3) == "metadata.json":
            continue
        art_name = m.group(1)
        version  = int(m.group(2))
        artifact_versions[art_name].append((version, fp))

    if not artifact_versions:
        print("[local-fallback] No versioned artifacts found locally.")
        return {}

    gcs_client = storage.Client()
    bucket     = gcs_client.bucket(bucket_name)

    # Pick the highest-version content file for each artifact, upload to GCS
    latest_gcs: dict = {}   # art_name → gs:// URL of highest-version copy in GCS
    for art_name, versions in artifact_versions.items():
        best_version, best_path = max(versions, key=lambda x: x[0])
        fname = pathlib.Path(art_name).name
        # Mirror the GCS path the normal artifact service would use:
        # root/user/<session_id>/<artifact_filename>/<version>
        gcs_blob_name = f"root/user/{session_id}/{fname}/{best_version}"
        blob = bucket.blob(gcs_blob_name)
        if not blob.exists():
            if fname.lower().endswith(".png"):
                mime = "image/png"
            elif fname.lower().endswith(".json"):
                mime = "application/json"
            else:
                mime = "text/plain"
            blob.upload_from_filename(str(best_path), content_type=mime)
            print(f"[local-fallback] Uploaded → gs://{bucket_name}/{gcs_blob_name}")
        else:
            print(f"[local-fallback] Already in GCS: {gcs_blob_name}")
        latest_gcs[art_name] = f"gs://{bucket_name}/{gcs_blob_name}"

    # Group by prompt key (strip well-known suffixes to find the prompt name)
    SUFFIXES = [
        ("_VizChart.png",   "chart"),
        ("_data.json",      "json"),
        ("_viz_agent.txt",  "viz_text"),
        ("_db_agent.txt",   "db_text"),
        ("_ds_agent.txt",   "ds_text"),
    ]
    prompt_map: dict = defaultdict(dict)
    for art_name, gcs_url in latest_gcs.items():
        fname = pathlib.Path(art_name).name
        for suffix, key in SUFFIXES:
            if fname.endswith(suffix):
                prompt = fname[: -len(suffix)]
                prompt_map[prompt][key] = (gcs_url, art_name)
                break

    # Build result_data in the same shape as the GCS-scan branch
    result_data: dict = {}
    for idx, (prompt, blobs) in enumerate(prompt_map.items(), start=1):
        entry: dict = {
            "prompt":    prompt.replace("_", " "),
            "chart_url": None,
            "json_data": None,
            "viz_text":  None,
            "db_text":   None,
            "ds_text":   None,
        }

        if "chart" in blobs:
            # blobs["chart"] is (gcs_url, art_name)
            entry["chart_url"] = blobs["chart"][0]
            if "json" in blobs:
                _, best_json_fp = max(artifact_versions[blobs["json"][1]], key=lambda x: x[0])
                try:
                    entry["json_data"] = json.loads(best_json_fp.read_text(encoding="utf-8"))
                except Exception:
                    pass
            if "viz_text" in blobs:
                _, best_vt_fp = max(artifact_versions[blobs["viz_text"][1]], key=lambda x: x[0])
                try:
                    entry["viz_text"] = best_vt_fp.read_text(encoding="utf-8")
                except Exception:
                    pass
        elif "ds_text" in blobs:
            _, best_ds_fp = max(artifact_versions[blobs["ds_text"][1]], key=lambda x: x[0])
            try:
                entry["ds_text"] = best_ds_fp.read_text(encoding="utf-8")
            except Exception:
                pass
        elif "db_text" in blobs:
            _, best_db_fp = max(artifact_versions[blobs["db_text"][1]], key=lambda x: x[0])
            try:
                raw = best_db_fp.read_text(encoding="utf-8")
                if raw.startswith("```json"):
                    raw = raw.split("\n", 1)[1]
                if raw.endswith("```"):
                    raw = raw.rsplit("\n", 1)[0]
                data = json.loads(raw)
                entry["db_text"] = data["nl_results"]
            except Exception:
                entry["db_text"] = raw if "raw" in dir() else ""

        result_data[f"prompt{idx}"] = entry

    return result_data


async def text_viz_json(tool_context: Optional[ToolContext] = None, **kwargs):
    print("inside text_viz_json agent")
    session_id = tool_context.state.get("session_id")
    print(f"[text_viz_json] session_id from state: {session_id!r}")
    # print(f"session id inside text_viz_json: {session_id}")
    bucket_name = os.getenv("BUCKET_NAME")
    # session_prefix = f'data_science/user/{session_id}/'
    session_prefix = f'root/user/{session_id}/'
    # session_prefix = f'default-app-name/user/{session_id}/'

    # Initialize client
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # Step 1: List and sort all blobs
    blobs = list(bucket.list_blobs(prefix=session_prefix))

    print(f"All blobs in session prefix {session_prefix}: {[blob.name for blob in blobs]}")

    # Keep all blobs. (Previously code_execution_image_* charts were dropped here, which is the
    # main reason code-interpreter-generated charts never reached the report. They are now kept
    # and harvested below.)
    filtered_blobs = list(blobs)
    sorted_blobs = sorted(filtered_blobs, key=lambda b: b.updated)

    # Step 2: Group blobs by base path (without /N), keep highest version
    blob_versions = defaultdict(list)
    versioned_blob_pattern = re.compile(r'(.+?)(?:/(\d+))$')  # Extract base path and version number

    for blob in sorted_blobs:
        match = versioned_blob_pattern.match(blob.name)
        if match:
            base_path = match.group(1)
            version = int(match.group(2))
            blob_versions[base_path].append((version, blob))

    # Step 3: Select highest version for each base path
    latest_blobs = {}
    for base_path, versions in blob_versions.items():
        # Pick the blob with max version number
        latest_blob = max(versions, key=lambda x: x[0])[1]
        latest_blobs[base_path] = latest_blob

    # Step 4: Identify prompts from .json and .png files
    prompt_map = defaultdict(dict)
    for base_path, blob in latest_blobs.items():
        filename = base_path.split('/')[-1]
        if filename.endswith('_data.json'):
            prompt = filename.replace('_data.json', '')
            prompt_map[prompt]['json_blob'] = blob
        elif filename.endswith('_VizChart.png'):
            prompt = filename.replace('_VizChart.png', '')
            prompt_map[prompt]['chart_blob'] = blob
        elif filename.endswith('_viz_ds_agent.txt'):
            prompt = filename.replace('_viz_ds_agent.txt', '')
            prompt_map[prompt]['viz_ds_text'] = blob
        elif filename.endswith('_viz_agent.txt'):
            prompt = filename.replace('_viz_agent.txt', '')
            prompt_map[prompt]['viz_text'] = blob
        elif filename.endswith('_db_agent.txt'):
            prompt = filename.replace('_db_agent.txt', '')
            prompt_map[prompt]['db_text'] = blob
        elif filename.endswith('_ds_agent.txt'):
            prompt = filename.replace('_ds_agent.txt', '')
            prompt_map[prompt]['ds_text'] = blob

    # Step 5: Build result_data
    result_data = {}
    for idx, (prompt, blobs_dict) in enumerate(prompt_map.items(), start=1):
        json_blob = blobs_dict.get('json_blob')
        chart_blob = blobs_dict.get('chart_blob')
        # viz_ds_blob = blobs_dict.get('viz_ds_text')
        viz_blob = blobs_dict.get('viz_text')
        db_blob =  blobs_dict.get('db_text')
        ds_blob =  blobs_dict.get('ds_text')

        result_data[f'prompt{idx}'] = {
            'prompt': prompt.replace("_"," "),
            'chart_url': None,
            'json_data': None,
            'viz_text': None,
            # 'viz_ds_text': None,
            'db_text': None,
            'ds_text': None
        }

        # Download chart if present
        if chart_blob:              # If chart is availabe
            result_data[f'prompt{idx}']['chart_url'] = f'gs://{bucket_name}/{chart_blob.name}'
            # Download JSON if present
            if json_blob:
                result_data[f'prompt{idx}']['json_data'] = f'gs://{bucket_name}/{json_blob.name}'
                # Download viz agent text if present
            if viz_blob:
                viz_string = viz_blob.download_as_text()
                result_data[f'prompt{idx}']['viz_text'] = viz_string
            ## Need Alignment: Do we need to add db_text and ds_text as well in chart
        elif ds_blob:
            ds_string = ds_blob.download_as_text()
            result_data[f'prompt{idx}']['ds_text'] = ds_string


        elif db_blob:
            db_string = db_blob.download_as_text()
            try:
              # Remove markdown formatting lines if present
              if db_string.startswith("```json"):
                  db_string = db_string.split("\n", 1)[1]  # Remove first line
              if db_string.endswith("```"):
                  db_string = db_string.rsplit("\n", 1)[0]  # Remove last line

              # Now parse the cleaned JSON string
              data = json.loads(db_string)

              # Extract channel names from `nl_results`
              nl_text = data["nl_results"]
              result_data[f'prompt{idx}']['db_text'] = nl_text
            except:
              result_data[f'prompt{idx}']['db_text'] = db_string

    # ---- Step 5a: Local-artifact fallback (adk web uses local file store) ----
    # When no GCS blobs were found the artifact service is local-file mode.
    # Upload the local PNGs/texts to GCS so the PDF generator can reach them.
    if not result_data:
        user_id = getattr(tool_context._invocation_context, "user_id", None) or "user"
        result_data = _upload_local_artifacts_to_gcs(session_id, bucket_name, user_id)
        if result_data:
            print(f"[local-fallback] Built result_data with {len(result_data)} prompts from local store.")

    # ---- Step 5b: Harvest charts NOT produced by the viz_agent ----
    # Charts drawn by the code interpreter (via call_ds_agent) are saved with generic names such as
    # `code_execution_image_1.png` / `daily_trends_chart.png` instead of the `<prompt>_VizChart.png`
    # convention, so the prompt_map logic above never captures them and every chart_url stays None.
    # Attach each such image artifact as its own chart entry so it is embedded in the report.
    already_charted = {
        v['chart_url'] for v in result_data.values() if v.get('chart_url')
    }
    extra_idx = len(result_data)
    for base_path, blob in sorted(latest_blobs.items(), key=lambda kv: kv[1].updated):
        filename = base_path.split('/')[-1]
        if filename.endswith('_VizChart.png'):
            continue  # already handled by the prompt_map logic above
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue
        chart_url = f'gs://{bucket_name}/{blob.name}'
        if chart_url in already_charted:
            continue
        already_charted.add(chart_url)
        extra_idx += 1
        label = filename.rsplit('.', 1)[0].replace('_', ' ').strip()
        result_data[f'prompt{extra_idx}'] = {
            'prompt': f'campaign performance visualization ({label})',
            'chart_url': chart_url,
            'json_data': None,
            'viz_text': None,
            'db_text': None,
            'ds_text': None,
        }

    print(f"[text_viz_json] result_data has {len(result_data)} prompt entries")
    tool_context.state['text_viz_json'] = result_data
    return result_data

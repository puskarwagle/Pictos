import json
import os
from pathlib import Path
from db import init_db, get_db, generate_id, hash_content
import sqlite3

# Configuration
SCRIPTS_DIR = Path("video-scripts")
RESPONSES_DIR = Path("ai_responses")
DOWNLOAD_DIR = Path("downloaded_images")

def migrate():
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    report = {
        "scripts_processed": 0,
        "anchors_created": 0,
        "images_linked": 0,
        "orphaned_images_on_disk": [], # Found on disk, not in JSON
        "missing_images_from_json": []  # Found in JSON, not on disk
    }

    # 1. Get all scripts
    script_files = list(SCRIPTS_DIR.glob("*.md"))
    
    for script_file in script_files:
        report["scripts_processed"] += 1
        script_stem = script_file.stem
        script_id = generate_id()
        
        try:
            cursor.execute("INSERT INTO scripts (id, filename) VALUES (?, ?)", (script_id, script_file.name))
        except sqlite3.IntegrityError:
            # Skip if already exists or handle accordingly
            cursor.execute("SELECT id FROM scripts WHERE filename = ?", (script_file.name,))
            script_id = cursor.fetchone()[0]

        # 2. Load AI Response
        response_file = RESPONSES_DIR / f"{script_stem}.json"
        if not response_file.exists():
            print(f"No AI response found for {script_file.name}, skipping segments.")
            continue
            
        with open(response_file, "r") as f:
            data = json.load(f)
            segments = data.get("segments", data) if isinstance(data, dict) else data

        # Track images we find in JSON to cross-reference with disk
        json_image_paths = set()

        for segment in segments:
            segment_id_val = segment.get("id")
            content = segment.get("text", "")
            keywords = segment.get("keywords", [])
            content_hash = hash_content(content)
            anchor_id = generate_id()
            
            # Create text_anchor
            cursor.execute("""
                INSERT INTO text_anchors (id, script_id, content, content_hash)
                VALUES (?, ?, ?, ?)
            """, (anchor_id, script_id, content, content_hash))
            report["anchors_created"] += 1

            # Create segment
            cursor.execute("""
                INSERT INTO segments (id, script_id, anchor_id, ai_index, keywords)
                VALUES (?, ?, ?, ?, ?)
            """, (generate_id(), script_id, anchor_id, segment_id_val, json.dumps(keywords)))

            # 3. Find images on disk for this segment
            # Current hierarchy: downloaded_images/{script_stem}/{segment_id}/{keyword_slug}/*.jpg
            segment_dir = DOWNLOAD_DIR / script_stem / str(segment_id_val)
            
            if segment_dir.exists():
                images_found_for_segment = False
                for kw_dir in segment_dir.iterdir():
                    if kw_dir.is_dir():
                        keyword = kw_dir.name.replace("_", " ")
                        for img_file in kw_dir.glob("*.jpg"):
                            images_found_for_segment = True
                            img_path_str = img_file.as_posix()
                            json_image_paths.add(img_path_str)
                            
                            img_id = generate_id()
                            cursor.execute("""
                                INSERT INTO images (id, anchor_id, file_path, keyword, legacy_path)
                                VALUES (?, ?, ?, ?, ?)
                            """, (img_id, anchor_id, img_path_str, keyword, img_path_str))
                            report["images_linked"] += 1
                
                if not images_found_for_segment:
                    report["missing_images_from_json"].append({
                        "script": script_file.name,
                        "segment_id": segment_id_val,
                        "reason": "Segment folder exists but contains no images"
                    })
            else:
                report["missing_images_from_json"].append({
                    "script": script_file.name,
                    "segment_id": segment_id_val,
                    "reason": "Segment folder not found"
                })

        # 4. Check for orphaned images on disk (files in script folder not in JSON)
        script_download_dir = DOWNLOAD_DIR / script_stem
        if script_download_dir.exists():
            for root, dirs, files in os.walk(script_download_dir):
                for file in files:
                    if file.endswith(".jpg"):
                        full_path = Path(root) / file
                        path_str = full_path.as_posix()
                        if path_str not in json_image_paths:
                            report["orphaned_images_on_disk"].append(path_str)

    conn.commit()
    conn.close()

    # Save Reconciliation Report
    with open("reconciliation_report.json", "w") as f:
        json.dump(report, f, indent=4)
    
    print("\n--- Migration Summary ---")
    print(f"Scripts processed: {report['scripts_processed']}")
    print(f"Anchors created: {report['anchors_created']}")
    print(f"Images linked: {report['images_linked']}")
    print(f"Orphaned images found: {len(report['orphaned_images_on_disk'])}")
    print(f"Missing image folders/segments: {len(report['missing_images_from_json'])}")
    print("Reconciliation report saved to reconciliation_report.json")

if __name__ == "__main__":
    migrate()

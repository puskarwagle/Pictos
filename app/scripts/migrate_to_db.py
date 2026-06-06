"""
Script for migrating existing filesystem-based image data into the SQLite database.

This script performs a deep reconciliation between the local file structure and the 
AI response JSON files. It is designed to be run when transitioning to the DB-backed
version of the application or when manual edits to the filesystem need to be
resynchronized with the database.

Workflow:
1. Iterates through all markdown scripts in the 'video-scripts' directory.
2. For each script, locates its corresponding AI response JSON in 'ai_responses'.
3. Creates 'text_anchors' for each segment found in the JSON.
4. Scans the 'downloaded_images' hierarchy to find images belonging to those segments.
5. Links found images to the newly created anchors in the 'images' table.
6. Generates a 'reconciliation_report.json' identifying orphaned files and missing data.
"""

from app.core.config import SCRIPTS_DIR, RESPONSES_DIR, DOWNLOAD_DIR
from app.db.session import init_db, get_db
from app.db.repository import generate_id, hash_content
import sqlite3
import json
import os
from pathlib import Path

def migrate():
    """
    Executes the migration process. 
    Handles deduplication by checking for existing script records via filename.
    """
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    report = {
        "scripts_processed": 0,
        "anchors_created": 0,
        "images_linked": 0,
        "orphaned_images_on_disk": [], # Found on disk, but no record in the AI response JSON
        "missing_images_from_json": []  # Listed in segments but no physical folder/files found
    }

    # 1. Get all scripts from the source-of-truth directory
    script_files = list(SCRIPTS_DIR.glob("*.md"))
    
    for script_file in script_files:
        report["scripts_processed"] += 1
        script_stem = script_file.stem
        script_id = generate_id()
        
        # Ensure we have a script record in the DB
        try:
            cursor.execute("INSERT INTO scripts (id, filename) VALUES (?, ?)", (script_id, script_file.name))
        except sqlite3.IntegrityError:
            # Script already exists, retrieve its ID to proceed with segment mapping
            cursor.execute("SELECT id FROM scripts WHERE filename = ?", (script_file.name,))
            script_id = cursor.fetchone()[0]

        # 2. Load AI Response for this script
        # This file defines the segments and their original content
        response_file = RESPONSES_DIR / f"{script_stem}.json"
        if not response_file.exists():
            print(f"No AI response found for {script_file.name}, skipping segments.")
            continue
            
        with open(response_file, "r") as f:
            data = json.load(f)
            segments = data.get("segments", data) if isinstance(data, dict) else data

        # Track images we find in JSON to cross-reference with the physical disk later
        json_image_paths = set()

        for segment in segments:
            segment_id_val = segment.get("id")
            content = segment.get("text", "")
            keywords = segment.get("keywords", [])
            content_hash = hash_content(content)
            anchor_id = generate_id()
            
            # Create a text_anchor: This is the "concept" the image is tied to.
            # Even if the text is edited slightly, the anchor remains stable.
            cursor.execute("""
                INSERT INTO text_anchors (id, script_id, content, content_hash)
                VALUES (?, ?, ?, ?)
            """, (anchor_id, script_id, content, content_hash))
            report["anchors_created"] += 1

            # Create a segment mapping: Ties the AI index (segment #) to the anchor
            cursor.execute("""
                INSERT INTO segments (id, script_id, anchor_id, ai_index, keywords)
                VALUES (?, ?, ?, ?, ?)
            """, (generate_id(), script_id, anchor_id, segment_id_val, json.dumps(keywords)))

            # 3. Find images on disk for this segment
            # Hierarchy: downloaded_images/{script_stem}/{segment_id}/{keyword_slug}/*.jpg
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
                            # Import existing files. Legacy path is set to handle future re-shuffles.
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

        # 4. Check for orphaned images on disk
        # Finds files physically present in the script's download folder that weren't 
        # referenced in the segments array of the AI response JSON.
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

    # Save Reconciliation Report for manual review
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
